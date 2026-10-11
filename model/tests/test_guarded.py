import pytest
from model import Event, GPIOState
from model.faults import Fault
from model.guarded_engine import GuardedEngine, GuardedFuture, PredicateCommand


def future(t=30, generation=1, pid=0):
    return GuardedFuture(t, pid, generation, GPIOState(0x55), GPIOState(0xAA))


def advance(m, t):
    while m.time < t:
        m.step()


@pytest.mark.parametrize("margin", [20, 10, 5, 2, 1, 0, -1, None])
@pytest.mark.parametrize("value", [False, True])
def test_resolution_boundary(margin, value):
    m = GuardedEngine()
    m.step(future(), predicate=PredicateCommand(0, 1, arm=True))
    resolution = 30 - margin if margin is not None else None
    pulses = []
    while m.time <= 32:
        pulses.append(m.step(predicate=PredicateCommand(0, 1, value=value)
                             if m.time == resolution else None))
    success = margin is not None and margin >= 1
    assert m.trace == ([(30, GPIOState(0xAA if value else 0x55))] if success else [])
    assert sum(r.executed for r in pulses) == int(success)
    assert sum(r.guard_missed for r in pulses) == int(not success)
    assert bool(m.faults & Fault.GUARD_MISS) == (not success)
    assert not m.queue


def test_stale_future_generation_and_write_once():
    m = GuardedEngine()
    m.step(future(10, 2), predicate=PredicateCommand(0, 1, arm=True))
    assert m.step(predicate=PredicateCommand(0, 2, value=True)).predicate_rejected
    assert m.step(predicate=PredicateCommand(0, 1, value=False)).predicate_accepted
    assert m.step(predicate=PredicateCommand(0, 1, value=True)).predicate_rejected
    advance(m, 10)
    assert m.step().guard_missed
    assert not m.trace


def test_reuse_invalidates_old_but_resolves_new():
    m = GuardedEngine()
    m.step(future(8), predicate=PredicateCommand(0, 1, arm=True))
    m.step(future(9, 2), predicate=PredicateCommand(0, 1, value=True))
    m.step(predicate=PredicateCommand(0, 2, arm=True))
    assert m.step(predicate=PredicateCommand(0, 1, value=False)).predicate_rejected
    m.step(predicate=PredicateCommand(0, 2, value=False))
    advance(m, 8)
    assert m.step().guard_missed
    assert m.step().false_executed
    assert m.trace == [(9, GPIOState(0x55))]


def test_no_generation_wrap_or_implicit_allocation():
    m = GuardedEngine(gen_w=2)
    assert m.step(predicate=PredicateCommand(0, 0)).predicate_rejected
    for g in [1, 2, 3]:
        assert m.step(predicate=PredicateCommand(0, g, arm=True)).predicate_accepted
    for g in [0, 1, 3]:
        assert m.step(predicate=PredicateCommand(0, g, arm=True)).predicate_rejected
    assert m.predicates[0].generation == 3


@pytest.mark.parametrize("reset_at", [0, 1, 5, 9, 10, 11])
def test_reset_before_after_resolution_and_at_commit(reset_at):
    m = GuardedEngine()
    m.step(future(10), predicate=PredicateCommand(0, 1, arm=True), reset=reset_at == 0)
    for t in range(1, reset_at):
        m.step(predicate=PredicateCommand(0, 1, value=True) if t == 5 else None)
    m.step(future(30), predicate=PredicateCommand(0, 1, value=True), reset=True)
    assert not m.queue and not m.trace and m.gpio.packed == 0 and not m.faults
    assert all(not p.active for p in m.predicates.values())


@pytest.mark.parametrize("depth", [1, 3])
def test_full_miss_retire_refill_and_ordinary_interaction(depth):
    m = GuardedEngine(depth=depth)
    for i in range(depth):
        assert m.step(future(10+i)).accepted
    assert not m.step(Event(20, GPIOState(7))).accepted
    m.step(Event(20, GPIOState(7)), drop=True)
    assert m.faults & Fault.QUEUE_OVERFLOW
    advance(m, 10)
    r = m.step(Event(20, GPIOState(7)))
    assert r.guard_missed and r.accepted and len(m.queue) == depth
    advance(m, 20)
    assert m.step().normal_executed
    assert m.trace == [(20, GPIOState(7))]


def test_same_edge_rearm_uses_old_state_and_timestamp_order():
    m = GuardedEngine()
    m.step(future(5), predicate=PredicateCommand(0, 1, arm=True))
    m.step(predicate=PredicateCommand(0, 1, value=True))
    assert m.step(future(5)).rejected
    advance(m, 5)
    r = m.step(predicate=PredicateCommand(0, 2, arm=True))
    assert r.true_executed and r.predicate_accepted
    assert not m.predicates[0].resolved
    assert m.step(Event(4, GPIOState())).rejected


def test_wrap_final_commit_and_closed_epoch():
    m = GuardedEngine(time_w=4)
    m.step(future(15), predicate=PredicateCommand(0, 1, arm=True))
    advance(m, 14)
    m.step(predicate=PredicateCommand(0, 1, value=True))
    assert m.step().true_executed
    assert m.time == 0 and m.epoch_closed
    assert m.step(future(5), predicate=PredicateCommand(0, 2, arm=True)).predicate_rejected
    assert not m.queue and len(m.trace) == 1


def test_equal_actions_still_select_one():
    m = GuardedEngine()
    f = GuardedFuture(3, 1, 1, GPIOState(7), GPIOState(7))
    m.step(f, predicate=PredicateCommand(1, 1, arm=True))
    m.step(predicate=PredicateCommand(1, 1, value=False))
    advance(m, 3)
    r = m.step()
    assert r.false_executed and not r.true_executed
