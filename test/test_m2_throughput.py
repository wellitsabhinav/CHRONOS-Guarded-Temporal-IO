"""Measure finite issue bursts separately from repeatedly drained programs."""
import json
from pathlib import Path
import cocotb
from test_programmable import Harness
from model.programmable_core import encode


@cocotb.test()
async def measured_restart_throughput(dut):
    h=Harness(dut)
    results=[]
    programs={
        'ordinary': [encode(1,1)]+[encode(2,20 if i==0 else 1) for i in range(14)]+[encode(0)],
        'guarded': [encode(4),encode(6,4)]+[encode(3,20 if i==0 else 1) for i in range(13)]+[encode(0)],
        'arm': [encode(4) for _ in range(15)]+[encode(0)],
        'resolve': [w for _ in range(7) for w in (encode(4),encode(6,4))]+[encode(0)]}
    for name,words in programs.items():
        await h.cycle(reset=True)
        origin=await h.load(words)
        rows=[]
        for repetition in range(32):
            if repetition:
                rows.append(await h.cycle(start=True))
            while not h.m.ready:
                rows.append(await h.cycle())
            assert not h.m.faults
        accepted=[r['time'] for r in rows if r['accepted']]
        predicates=[r['time'] for r in rows if r['predicate_accepted']]
        measured=rows[-1]['time']-origin+1
        results.append(dict(program=name,restarts=32,words=len(words),
            cycles_including_start=measured,accepted=len(accepted),
            executed=sum(r['executed'] for r in rows),predicate_commands=len(predicates),
            arms=sum(r['arm_accepted'] for r in rows),resolutions=sum(r['resolve_accepted'] for r in rows),
            instruction_count=sum(r['retired'] for r in rows),stalls=sum(r['stalled'] for r in rows),
            max_occupancy=max(r['occupancy'] for r in rows),
            full_pop_refill=sum(r['accepted'] and r['executed'] and r['occupancy']==h.depth for r in rows),
            min_issue_spacing=min((b-a for a,b in zip(accepted,accepted[1:])),default=None),
            min_predicate_spacing=min((b-a for a,b in zip(predicates,predicates[1:])),default=None),
            events_per_cycle=len(accepted)/measured,predicate_commands_per_cycle=len(predicates)/measured,
            loader_cycles=2+9*len(words),faults=h.m.faults))
    assert results[0]['full_pop_refill'] and results[1]['full_pop_refill']
    Path('m2_throughput.json').write_text(json.dumps(dict(time_w=h.time_w,depth=h.depth,
        scope='32 drained restarts; excludes initial loading, includes every START and drain edge',
        rows=results),indent=2)+'\n')
