"""Exact-time peer pin oracle plus independent model comparison every edge."""
import json
from pathlib import Path
import cocotb
from cocotb.triggers import Timer
from model.programmable_core import ProgrammableCore
from model.m3_baseline import EventlessDescriptor, EventlessResponder
from model.m3_peer import CLOCK, aggregate, candidates, summarize


class PeerHarness:
    def __init__(self, dut, length=4):
        self.d, self.wall = dut, 0
        self.m = ProgrammableCore()
        self.b = EventlessResponder(EventlessDescriptor(response_length=length))
        self.raw, self.reset = 8, False
        dut.clk.value = 0
        dut.rst_n.value = 1
        dut.ena.value = 1
        dut.ui_in.value = 0
        dut.uio_in.value = self.raw
        dut.baseline_start.value = 0
        dut.baseline_length.value = length

    def pins(self):
        d = self.d
        return int(d.uo_out.value) | int(d.uio_out.value)<<8 | int(d.uio_oe.value)<<16

    async def advance(self, when):
        assert when >= self.wall, (when, self.wall)
        if when > self.wall:
            await Timer(when-self.wall, unit='ps')
            self.wall = when

    async def edge(self, *, write=None, start=False):
        d, m, b = self.d, self.m, self.b
        m.step(self.raw,write=write,start=start,reset=self.reset)
        b.step(self.raw,start=start,reset=self.reset)
        d.clk.value = 1
        await self.advance(self.wall+1)  # settle RTL; oracle ties sample BEFORE edge
        c = d.chronos.core
        expected = dict(time_now=m.engine.time,gpio_state=m.engine.gpio,
            origin=m.origin,cursor=m.cursor,pc=m.pc,halted=m.halted,faults=m.faults,
            occupancy=len(m.engine.queue),sampler_busy=m.sampler is not None,
            sampled=m.sampled,sample_word=m.sample_word,stalled=m.stalled,
            instruction_retired=m.instruction_retired,epoch_closed=m.engine.closed,
            accepted=m.engine.pulses.get('accepted',False),executed=m.engine.pulses.get('executed',False),
            sync1=m.sync1,sync2=m.sync2,previous=m.previous)
        for k,v in expected.items():
            assert int(getattr(c,k).value)==int(v),(self.wall,k,int(getattr(c,k).value),v)
        assert self.pins()==m.engine.gpio
        expected_b=dict(baseline_gpio=b.gpio_state,baseline_armed=b.armed,
            baseline_active=b.active,baseline_completed=b.completed,baseline_index=b.bit_index,
            baseline_sampled=b.sampled,baseline_emitted=b.emitted,baseline_cancelled=b.cancelled,
            baseline_sample_word=b.sample_word,baseline_sync1=b.sync1,
            baseline_sync2=b.sync2,baseline_previous=b.previous)
        for k,v in expected_b.items():
            assert int(getattr(d,k).value)==int(v),(self.wall,k,int(getattr(d,k).value),v)
        d.clk.value = 0

    async def host_cycle(self, command=0, nibble=0, *, write=None, reset=False):
        self.reset=reset
        self.d.rst_n.value=not reset
        self.d.ui_in.value=(command<<4)|nibble
        self.d.baseline_start.value=command==7
        await self.advance(self.wall+CLOCK//2)
        edge_time=self.wall
        await self.edge(write=write,start=command==7)
        await self.advance(edge_time+CLOCK//2)
        return edge_time

    async def load(self, words):
        await self.host_cycle(reset=True)
        await self.host_cycle(6,0)
        await self.host_cycle(3)
        for address,word in enumerate(words):
            for i in range(8):
                await self.host_cycle(1,(word>>(4*i))&15)
            await self.host_cycle(2,write=(address,word))
        origin_wall=await self.host_cycle(7)
        self.d.ui_in.value=0
        self.d.baseline_start.value=0
        return origin_wall

    async def transaction(self, point, origin_wall):
        rows, samples, br, bs = [], [], [], []
        for t, _, kind, data in point.timeline():
            await self.advance(origin_wall+t)
            if kind=='input':
                self.raw=data[0]
                # After an early CS release, keep it high on later SCK changes.
                if point.cs_early is not None and t>=point.cs_early:
                    self.raw |= 8
                self.d.uio_in.value=self.raw
            elif kind=='reset':
                self.reset=data
                self.d.rst_n.value=not data
            elif kind=='sample':
                # These are the only correctness observations.
                gpio=self.pins()
                bgpio=int(self.d.baseline_gpio.value)
                assert gpio==self.m.engine.gpio and bgpio==self.b.gpio_state
                samples.append(dict(t=t,gpio=gpio))
                bs.append(dict(t=t,gpio=bgpio))
            else:
                await self.edge()
                m=self.m
                rows.append(dict(t=t,gpio=self.pins(),sampled=m.sampled,
                    emitted=m.engine.pulses.get('executed',False),
                    accepted=m.engine.pulses.get('accepted',False),
                    stalled=m.stalled,occupancy=len(m.engine.queue),faults=m.faults,
                    sampler_busy=m.sampler is not None,completed=m.ready))
                br.append(dict(t=t,gpio=self.b.gpio_state,sampled=self.b.sampled,
                    emitted=self.b.emitted,completed=self.b.completed,
                    cancelled=self.b.cancelled))
        return summarize(point,rows,samples,br,bs)


@cocotb.test()
async def peer_boundary_and_adversarial(dut):
    results=[]
    for point in candidates():
        h=PeerHarness(dut,point.length)
        origin=await h.load(point.program())
        result=await h.transaction(point,origin)
        # Frozen timestamp semantics: emitted actions must keep their target.
        assert all(s['timing_error']==0 for s in result['chronos']['samples'] if s['O'] is not None)
        results.append(result)
    Path('m3_peer_timing.json').write_text(json.dumps(dict(
        scope='RTL default M2 loader and public pins; every-edge models; ideal digital synchronizers',
        clock_ps=CLOCK,aggregate=aggregate(results),rows=results),indent=2)+'\n')
