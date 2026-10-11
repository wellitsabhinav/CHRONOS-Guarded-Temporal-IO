"""M2 edge-by-edge oracle comparison, including logical FIFO and ownership."""
import json
import os
from pathlib import Path
import random
import cocotb
from cocotb.triggers import Timer
from model.programmable_core import ProgrammableCore, encode
from model.tests.test_programmable import slice_program


class Harness:
    def __init__(self, dut):
        self.d = dut
        self.time_w = int(os.environ.get('CHRONOS_TIME_W', 16))
        self.gen_w = int(os.environ.get('CHRONOS_GEN_W', 2))
        self.depth = int(os.environ.get('CHRONOS_DEPTH', 3))
        self.guards = bool(int(os.environ.get('CHRONOS_GUARDS_ENABLED', 1)))
        self.m = ProgrammableCore(self.depth, self.time_w, 2, self.gen_w, self.guards)
        self.rows = []

    async def cycle(self, gpio=0, *, write=None, start=False, reset=False):
        d, m, e = self.d, self.m, self.m.engine
        for name, value in dict(clk=0, rst_n=not reset, gpio_in=gpio, program_write=write is not None,
                               program_start=start, program_address=write[0] if write else 0,
                               program_data=write[1] if write else 0).items():
            getattr(d, name).value = int(value)
        await Timer(5, unit='ns')
        if not reset:
            assert int(d.control_ready.value) == int(m.ready), (e.time, 'control_ready')
        t = e.time
        command_arm=int(d.predicate_arm.value) if not reset else 0
        m.step(gpio, write=write, start=start, reset=reset)
        d.clk.value = 1
        await Timer(5, unit='ns')
        expected = dict(time_now=e.time, gpio_state=e.gpio, occupancy=len(e.queue), faults=m.faults,
                        epoch_closed=e.closed, pc=m.pc, origin=m.origin, cursor=m.cursor,
                        instruction=m.instruction, halted=m.halted, sampled=m.sampled,
                        sampler_busy=m.sampler is not None, sample_word=m.sample_word,
                        instruction_retired=m.instruction_retired, stalled=m.stalled,
                        start_accepted=m.start_accepted, write_accepted=m.write_accepted)
        expected.update({k: e.pulses.get(k, False) for k in ('accepted','rejected','executed','normal_executed',
            'false_executed','true_executed','guard_missed','predicate_accepted','predicate_rejected')})
        for field in ('active','resolved','value'):
            expected['predicate_'+field+'_state'] = sum(int(getattr(p, field)) << i for i,p in enumerate(e.predicates))
        expected['predicate_generation_state'] = sum(p.generation << (i*self.gen_w) for i,p in enumerate(e.predicates))
        cw = max(1, self.depth.bit_length())
        expected['predicate_refcount_state'] = sum(p.refs << (i*cw) for i,p in enumerate(e.predicates))
        observed = {k: int(getattr(d,k).value) for k in expected}
        expected = {k:int(v) for k,v in expected.items()}
        assert observed == expected, f'edge {t}: {observed}, expected {expected}'
        for field, value in [('sync1',m.sync1),('sync2',m.sync2),('previous',m.previous),
                             ('action0',m.actions[0]),('action1',m.actions[1]),('compare_config',m.config)]:
            assert int(getattr(d,field).value) == value, (t,field)
        if m.sampler:
            s=m.sampler
            for field,value in [('sample_at',s['at']),('sample_deadline',s['deadline']),
                                ('sample_config',s['config']),('sample_pid',s['pid']),
                                ('sample_gen',s['generation']),('sample_direct',s['direct']),
                                ('sample_action0',s['actions'][0]),('sample_action1',s['actions'][1])]:
                assert int(getattr(d,field).value) == value, (t,field)
        rp=int(d.engine.read_ptr.value)
        for index,a in enumerate(e.queue):
            word=a.timestamp | (a.false << self.time_w)
            if self.guards:
                word |= a.true << (self.time_w+24)
                word |= a.pid << (self.time_w+48)
                word |= a.generation << (self.time_w+50)
                word |= int(a.guarded) << (self.time_w+50+self.gen_w)
            assert int(d.engine.entries[(rp+index)%self.depth].value)==word, (t,index,a)
        row=dict(time=t, gpio=e.gpio, occupancy=len(e.queue), pc=m.pc, faults=m.faults,
                 sampled=m.sampled, retired=m.instruction_retired, stalled=m.stalled,
                 arm_accepted=bool(command_arm and e.pulses.get('predicate_accepted')),
                 resolve_accepted=bool(not command_arm and e.pulses.get('predicate_accepted')),
                 **{k:bool(v) for k,v in e.pulses.items()})
        self.rows.append(row)
        return row

    async def load(self, words):
        for i,w in enumerate(words):
            await self.cycle(write=(i,w))
        await self.cycle(start=True)
        return self.m.origin


@cocotb.test()
async def first_slice_deadlines_and_reuse(dut):
    h=Harness(dut)
    for direct in (False,True):
        if not h.guards and not direct:
            continue
        for margin in (10,5,3,2,1,0,-1):
            for value in (0,1):
                await h.cycle(reset=True)
                origin=await h.load(slice_program(30,30-margin,direct))
                start=len(h.rows)
                while h.m.engine.time <= origin+34:
                    await h.cycle(value)
                trace=[(r['time']-origin,r['gpio']) for r in h.rows[start:] if r['executed']]
                assert trace == ([(30,0xf0ccaa if value else 0x0f3355)] if margin>=1 else [])
    await h.cycle(reset=True)
    await h.load(slice_program(12,11,not h.guards))
    for i in range(512):
        while not h.m.ready:
            await h.cycle(i&1)
        assert not h.m.faults
        assert h.m.engine.predicates[0].generation == i%h.m.engine.genmax+1
        if i!=511:
            await h.cycle(start=True)


@cocotb.test()
async def small_random_programs(dut):
    h=Harness(dut)
    counts={k:0 for k in ('accepted','executed','guard_missed','predicate_accepted','sampled','stalled')}
    for seed in (2201,2202,2203):
        rng=random.Random(seed)
        await h.cycle(reset=True)
        for cycle in range(600):
            write=None; start=False
            if h.m.ready:
                if not all(h.m.valid[i] for i in range(7)):
                    i=next(i for i in range(7) if not h.m.valid[i])
                    words=slice_program(12+rng.randrange(10),11+rng.randrange(14),not h.guards or rng.random()<.4)
                    if rng.random()<.1:
                        words[i]=rng.getrandbits(32)
                    write=(i,words[i])
                else:
                    start=True
            try:
                row=await h.cycle(rng.randrange(256),write=write,start=start,reset=cycle%101==100)
            except AssertionError as exc:
                raise AssertionError(f'seed {seed} cycle {cycle}: {exc}') from exc
            for k in counts:
                counts[k]+=bool(row.get(k))
    assert counts['accepted'] and counts['executed'] and counts['predicate_accepted'] and counts['sampled']
    Path('m2_differential.json').write_text(json.dumps(dict(seeds=[2201,2202,2203],cycles=1800,
        depth=h.depth,time_w=h.time_w,gen_w=h.gen_w,guards=h.guards,counts=counts),indent=2)+'\n')


@cocotb.test()
async def directed_program_sampler_conflicts(dut):
    h=Harness(dut)
    if h.guards:
        await h.cycle(reset=True)
        words=[encode(4),encode(3,30)]
        if h.depth>1:
            words += [encode(3,1)]
        words += [encode(5,29),encode(4),encode(0)]
        origin=await h.load(words)
        while not h.m.ready:
            await h.cycle()
        assert not h.m.faults and h.m.engine.predicates[0].generation==2
        assert sum(r['executed'] for r in h.rows if origin<=r['time']) == (2 if h.depth>1 else 1)
    for change in (27,28,29,30):
        await h.cycle(reset=True)
        origin=await h.load(slice_program(30,29,not h.guards))
        while h.m.engine.time<=origin+33:
            await h.cycle(int(h.m.engine.time-origin>=change))
        assert h.m.sample_word == int(change<=27)
        assert h.m.engine.gpio == (0xf0ccaa if change<=27 else 0x0f3355)
    for word in (encode(15),encode(0,1),encode(4,8)):
        await h.cycle(reset=True)
        await h.load([word])
        await h.cycle()
        assert h.m.halted and h.m.faults&32
    await h.cycle(reset=True)
    await h.load([encode(1,i) for i in range(16)])
    while not h.m.halted:
        await h.cycle()
    assert h.m.pc==15 and h.m.faults&32
    await h.cycle(reset=True)
    await h.load([encode(4),encode(5,30),encode(6,4),encode(0)])
    while not h.m.ready:
        await h.cycle()
    assert h.m.faults&64 and h.m.faults&16  # hardware duplicate rejects, descriptor drains
    await h.cycle(reset=True)
    await h.load(slice_program(30,29,not h.guards))
    await h.cycle(write=(0,encode(0)))
    assert h.m.halted and h.m.faults&32
    await h.cycle(reset=True)
    assert not h.m.faults and h.m.ready
    await h.cycle(write=(0,encode(0)),start=True)
    assert h.m.halted and h.m.faults&32 and not h.m.valid[0]
    assert not h.m.write_accepted and not h.m.start_accepted


@cocotb.test()
async def immutable_descriptors_and_selected_edges(dut):
    h=Harness(dut)
    for direct in (True,False):
        if not direct and not h.guards: continue
        await h.cycle(reset=True)
        words=[encode(1,0x0f3355),encode(1,(1<<24)|0xf0ccaa),encode(7,0x101),encode(4),
               encode(9 if direct else 3,30),encode(5,(int(direct)<<26)|29),
               encode(1,0x123456),encode(1,(1<<24)|0xabcdef),encode(7,0),encode(0)]
        origin=await h.load(words)
        while not h.m.ready: await h.cycle(1)
        assert h.m.engine.gpio==0xf0ccaa and h.m.sample_word==1 and not h.m.faults
        assert h.m.origin==origin
    # Inclusive timeout permits a selected synchronized rise on the last edge.
    for raw_rise in (27,28):
        await h.cycle(reset=True)
        words=[encode(1,1),encode(1,(1<<24)|2),encode(7,1|(1<<8)|(1<<16)|(2<<17)|(1<<20)|(3<<21)),
               encode(4),encode(9,30),encode(5,(1<<26)|29),encode(0)]
        origin=await h.load(words)
        while h.m.engine.time<=origin+34:
            t=h.m.engine.time-origin
            await h.cycle(1 | (4 if t>=raw_rise else 0))
        assert h.m.engine.gpio==(2 if raw_rise==27 else 0)
        assert bool(h.m.faults&64)==(raw_rise==28)
    # A high active-low select pin prevents a timed capture even when data matches.
    await h.cycle(reset=True)
    await h.load([encode(7,0x101|(1<<20)|(3<<21)),encode(4),encode(5,20),encode(0)])
    while not h.m.ready: await h.cycle(9)
    assert h.m.faults&64 and not h.m.engine.predicates[0].resolved
    # A sampler/software RESOLVE conflict stalls on R, then software faults as duplicate.
    await h.cycle(reset=True)
    await h.load([encode(4),encode(5,9)]+[encode(1) for _ in range(6)]+[encode(6,4),encode(0)])
    while not h.m.ready: await h.cycle()
    assert any(r['sampled'] and r['stalled'] for r in h.rows)
    assert h.m.halted and h.m.faults&32
