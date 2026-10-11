"""Defensive token rejection and simultaneous retire/admit without a producer."""
import cocotb
from cocotb.triggers import Timer
from model.programmable_core import ReclaimingEngine,Action


@cocotb.test()
async def reclaim_edge_conflicts(d):
    m=ReclaimingEngine(3,8,2,2)
    async def edge(event=None,command=None,holds=(),reset=False):
        values=dict(clk=0,rst_n=not reset,event_valid=event is not None,event_drop=0,
            event_timestamp=event.timestamp if event else 0,event_state=event.false if event else 0,
            event_state_true=event.true if event else 0,event_guarded=event.guarded if event else 0,
            event_predicate=event.pid if event else 0,event_generation=event.generation if event else 0,
            predicate_valid=command is not None,predicate_id=command[0] if command else 0,
            predicate_generation=command[1] if command else 0,predicate_arm=command[2] if command else 0,
            predicate_value=command[3] if command else 0,predicate_hold=sum(1<<p for p in holds))
        for k,v in values.items(): getattr(d,k).value=int(v)
        await Timer(5,unit='ns')
        m.step(event,command,holds,reset=reset)
        d.clk.value=1
        await Timer(5,unit='ns')
        expected=dict(time_now=m.time,gpio_state=m.gpio,occupancy=len(m.queue),faults=m.faults,
            epoch_closed=m.closed,**m.pulses)
        for k,v in expected.items(): assert int(getattr(d,k).value)==int(v),(k,m.time)
        assert int(d.predicate_refcount_state.value)==sum(p.refs<<(i*2) for i,p in enumerate(m.predicates))
        assert int(d.predicate_generation_state.value)==sum(p.generation<<(i*2) for i,p in enumerate(m.predicates))
    await edge(reset=True)
    await edge(command=(0,1,True,False))
    await edge(command=(1,1,True,False))
    await edge(command=(0,1,False,True))
    for t in (10,11,12): await edge(Action(t,0x0f3355,0xf0ccaa,True,0,1))
    while m.time<10: await edge()
    # Full pop/refill preserves the same predicate's three references.
    await edge(Action(13,0x123456,0xabcdef,True,0,1),command=(0,2,True,False))
    assert m.predicates[0].refs==3 and m.pulses['predicate_rejected']
    # A different predicate gains ownership on the simultaneous retirement.
    await edge(Action(14,0x223344,0x556677,True,1,1))
    assert m.predicates[0].refs==2 and m.predicates[1].refs==1
    await edge()
    await edge(command=(0,2,True,False))  # pre-edge final reference still prevents ARM
    assert m.pulses['predicate_rejected'] and m.predicates[0].refs==0
    await edge(command=(0,2,True,False))  # enables next edge; unresolved pid1 misses and retires
    assert m.pulses['predicate_accepted'] and m.pulses['guard_missed'] and m.predicates[1].refs==0
    await edge(Action(25,1,2,True,0,1),command=(0,1,False,True))
    assert m.pulses['rejected'] and m.pulses['predicate_rejected']  # stale generation
    await edge(command=(0,3,True,False),holds=(0,))
    assert m.pulses['predicate_rejected']
    await edge(reset=True)
    assert not m.queue and all(p.refs==0 and p.generation==0 for p in m.predicates)
