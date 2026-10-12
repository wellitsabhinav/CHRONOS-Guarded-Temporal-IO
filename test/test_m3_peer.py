"""Exact-time peer pin oracle plus independent model comparison every edge."""
import json
from pathlib import Path
import cocotb
from cocotb.triggers import Timer
from model.programmable_core import ProgrammableCore
from model.m3_baseline import EventlessDescriptor, EventlessResponder
from model.m3_countdown import CountdownDescriptor, CountdownResponder
from model.m3_peer import CLOCK, PeerPoint, aggregate, candidates, summarize


class PeerHarness:
    def __init__(self, dut, length=4, trigger_rising=True, deadline=40, spacing=8):
        self.d, self.wall = dut, 0
        self.compared_cycles=0
        self.m = ProgrammableCore()
        self.b = EventlessResponder(EventlessDescriptor(response_length=length,
                                  trigger_rising=trigger_rising,emit_rising=not trigger_rising))
        self.w = CountdownResponder(CountdownDescriptor(response_length=length,
                                  first_delay=deadline,spacing=spacing))
        self.raw, self.reset = 8, False
        dut.clk.value = 0
        dut.rst_n.value = 1
        dut.ena.value = 1
        dut.ui_in.value = 0
        dut.uio_in.value = self.raw
        dut.baseline_start.value = 0
        dut.baseline_length.value = length
        dut.baseline_trigger_rising.value = trigger_rising
        dut.wait_first_delay.value = deadline
        dut.wait_spacing.value = spacing

    def pins(self):
        d = self.d
        return int(d.uo_out.value) | int(d.uio_out.value)<<8 | int(d.uio_oe.value)<<16

    async def advance(self, when):
        assert when >= self.wall, (when, self.wall)
        if when > self.wall:
            await Timer(when-self.wall, unit='ps')
            self.wall = when

    async def edge(self, *, write=None, start=False):
        d, m, b, w = self.d, self.m, self.b, self.w
        self.compared_cycles+=1
        w.step(b.sync2,start=start,reset=self.reset)
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
        expected_w=dict(wait_gpio=w.gpio_state,wait_active=w.active,wait_completed=w.completed,
            wait_resolved=w.resolved,wait_index=w.bit_index,wait_sampled=w.sampled,wait_emitted=w.emitted,
            wait_sample_word=w.sample_word,wait_count=w.wait_count,wait_faults=w.faults,
            wait_previous=w.previous)
        for k,v in expected_w.items():
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
        rows, samples, br, bs, wr, ws = [], [], [], [], [], []
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
                ws.append(dict(t=t,gpio=int(self.d.wait_gpio.value)))
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
                wr.append(dict(t=t,gpio=self.w.gpio_state,sampled=self.w.sampled,
                    emitted=self.w.emitted,completed=self.w.completed,faults=self.w.faults))
        return summarize(point,rows,samples,br,bs,wr,ws)


@cocotb.test()
async def peer_boundary_and_adversarial(dut):
    results=[]
    for point in candidates():
        h=PeerHarness(dut,point.length,point.trigger_rising,point.deadline,point.spacing)
        origin=await h.load(point.program())
        result=await h.transaction(point,origin)
        result['compared_cycles']=h.compared_cycles
        # Frozen timestamp semantics: emitted actions must keep their target.
        allowed=[(point.deadline+i*point.spacing)*CLOCK for i in range(point.length)]
        actual=result['chronos']['output_times']
        assert actual==sorted(set(actual)) and all(t in allowed for t in actual)
        assert all(s['timing_error']==0 for s in result['chronos']['samples'] if s['O'] is not None)
        # This is the comparison that falsifies a timestamp-specific advantage.
        assert result['chronos']['success']==result['relative_wait']['success']
        if result['chronos']['success'] and point.length==4:
            assert result['chronos']['pin_transitions']==result['relative_wait']['pin_transitions']
        results.append(result)
    Path('m3_peer_timing.json').write_text(json.dumps(dict(
        scope='RTL default M2 loader and public pins; every-edge models; ideal digital synchronizers',
        clock_ps=CLOCK,compared_cycles=sum(r['compared_cycles'] for r in results),
        aggregate=aggregate(results),rows=results),indent=2)+'\n')


@cocotb.test()
async def drained_restart_peer_transactions(dut):
    # Preloaded 10 words, no reset/reload between transactions. First command
    # follows START by 12 clocks, peer completes its fourth sample at +44,
    # and CS deassertion at +48 reaches the pre-edge frontend by +51.
    # Re-arm after deselection to avoid treating the old final SCK rise as a
    # new command in the immediate baseline.
    count, interval = 8, 51*CLOCK
    points=[PeerPoint(name='restart',deadline=16,value=i%2) for i in range(count)]
    h=PeerHarness(dut,deadline=16)
    origin=await h.load(points[0].program())
    events=[]
    for j,p in enumerate(points):
        for t,priority,kind,data in p.timeline():
            if kind!='clock': events.append((j*interval+t,priority,kind,(j,data)))
        # Host command must settle through the wrapper before the clock edge.
        if j: events.append((j*interval-1,0,'start',(j,None)))
    end=(count-1)*interval+max(t for t,_,_,_ in points[-1].timeline())
    events += [(t,2,'clock',None) for t in range(CLOCK,end+1,CLOCK)]
    traces=[[] for _ in points]; btraces=[[] for _ in points]
    wtraces=[[] for _ in points]; wsamples=[[] for _ in points]
    samples=[[] for _ in points]; bsamples=[[] for _ in points]
    pending=False; current=0; starts=[]
    for t,_,kind,data in sorted(events,key=lambda x:(x[0],x[1])):
        await h.advance(origin+t)
        if kind=='input':
            h.raw=data[1][0]; dut.uio_in.value=h.raw
        elif kind=='sample':
            j,index=data
            samples[j].append(dict(t=t-j*interval,gpio=h.pins()))
            bsamples[j].append(dict(t=t-j*interval,gpio=int(dut.baseline_gpio.value)))
            wsamples[j].append(dict(t=t-j*interval,gpio=int(dut.wait_gpio.value)))
        elif kind=='start':
            current=data[0]; pending=True
            dut.ui_in.value=7<<4; dut.baseline_start.value=1
        else:
            await h.edge(start=pending)
            if pending:
                assert h.m.start_accepted and not h.m.faults
                starts.append(t)
                dut.ui_in.value=0; dut.baseline_start.value=0; pending=False
            m=h.m; rel=t-current*interval
            traces[current].append(dict(t=rel,gpio=h.pins(),sampled=m.sampled,
                emitted=m.engine.pulses.get('executed',False),accepted=m.engine.pulses.get('accepted',False),
                stalled=m.stalled,occupancy=len(m.engine.queue),faults=m.faults,
                sampler_busy=m.sampler is not None,completed=m.ready))
            btraces[current].append(dict(t=rel,gpio=h.b.gpio_state,sampled=h.b.sampled,
                emitted=h.b.emitted,completed=h.b.completed))
            wtraces[current].append(dict(t=rel,gpio=h.w.gpio_state,sampled=h.w.sampled,
                emitted=h.w.emitted,completed=h.w.completed,faults=h.w.faults))
    results=[summarize(p,traces[j],samples[j],btraces[j],bsamples[j],wtraces[j],wsamples[j]) for j,p in enumerate(points)]
    assert all(r['chronos']['success'] and r['eventless']['success'] and r['relative_wait']['success'] for r in results), [
        (j,[(s['observed'],s['oe']) for s in r['chronos']['samples']],
         [(s['observed'],s['oe']) for s in r['eventless']['samples']]) for j,r in enumerate(results)
        if not (r['chronos']['success'] and r['eventless']['success'])]
    Path('m3_restarts.json').write_text(json.dumps(dict(transactions=count,
        compared_cycles=h.compared_cycles,
        start_interval_clocks=interval/CLOCK,initial_loader_excluded=True,
        bits_correct_per_path=count*4,steady_bits_per_clock=4*CLOCK/interval,
        start_edges=starts,rows=results),indent=2)+'\n')
