import json
from pathlib import Path
from itertools import product
import pytest
from model import Event, Fault, GPIOState, TemporalEngine
from model.cli import run_script


def event(time, value=1):
    return Event(time, GPIOState.unpack(value))


def test_canonical_trace():
    root = Path(__file__).resolve().parents[2]
    trace, engine = run_script(json.loads((root / "examples/m0/basic.json").read_text()))
    assert trace == json.loads((root / "examples/m0/basic.expected.json").read_text())
    assert engine.faults == 0


def test_earliest_legal():
    engine = TemporalEngine()
    assert engine.enqueue(event(1)).accepted
    assert engine.time == 1 and engine.gpio == GPIOState()
    assert engine.step().executed == event(1)
    assert engine.time == 2


@pytest.mark.parametrize("depth", [1, 2, 3, 8, 9])
def test_full_backpressure_drop_and_refill(depth):
    engine = TemporalEngine(depth)
    for i in range(depth):
        assert engine.step(event(20 + i, i + 1)).accepted
    assert not engine.ready
    assert not engine.step(event(40)).accepted
    assert engine.faults == 0  # legal waiting
    engine.step(event(40), drop=True)
    assert engine.faults == Fault.QUEUE_OVERFLOW
    engine.run(20 - engine.time)
    result = engine.step(event(40))
    assert result.ready and result.accepted and result.executed == event(20)
    assert len(engine.queue) == depth


@pytest.mark.parametrize("depth", [1, 3, 8])
def test_dense_repeated_wraps(depth):
    engine = TemporalEngine(depth)
    for i in range(1000):
        result = engine.step(event(i + 1, (i % 255) + 1))
        assert result.accepted
        assert bool(result.executed) == (i > 0)
        if i > 0:
            assert result.executed.timestamp == i
    assert engine.faults == 0


@pytest.mark.parametrize("at", [0, 1, 18, 19, 20, 21])
@pytest.mark.parametrize("reset_cycles", [1, 4])
def test_reset_boundary_reload(at, reset_cycles):
    engine = TemporalEngine()
    if at:
        engine.step(event(20, 0xFFFFFF))
        engine.run(at - 1)
    for _ in range(reset_cycles):
        result = engine.step(event(22), reset=True)
        assert not result.accepted and result.executed is None
        assert engine.time == 0 and not engine.queue.contents
        assert engine.gpio == GPIOState() and engine.faults == 0
    assert engine.enqueue(event(1, 0x123456)).accepted
    assert engine.step().executed.state.packed == 0x123456


def test_faults_are_sticky_and_do_not_retime():
    engine = TemporalEngine()
    engine.step(event(20, 0x55))
    engine.step(event(19))
    assert engine.faults == Fault.TIME_ORDER_FAULT
    engine.step(event(2))
    assert engine.faults == Fault.TIME_ORDER_FAULT | Fault.DEADLINE_MISS
    engine.run(18)
    assert engine.trace == [(20, GPIOState(0x55))]
    assert engine.step(event(20)).rejected  # order history persists after drain


def test_late_head_dropped_without_output():
    engine = TemporalEngine()
    engine.run(10)
    engine.queue.append(event(5, 0xFFFFFF))  # deliberate defensive-state test
    assert engine.step().executed is None
    assert not engine.queue.contents and engine.gpio == GPIOState()
    assert engine.faults == Fault.DEADLINE_MISS


@pytest.mark.parametrize("time_w", [1, 2, 3, 4, 8])
def test_complete_epoch_boundary(time_w):
    engine = TemporalEngine(time_w=time_w)
    limit = engine.limit
    engine.step(event(limit, 0x123456))
    engine.run(limit)
    assert engine.trace == [(limit, GPIOState.unpack(0x123456))]
    assert engine.time == 0 and engine.epoch_closed
    for _ in range(limit + 2):
        assert engine.step(event(limit)).rejected
        assert engine.gpio.packed == 0x123456
    assert engine.faults & Fault.DEADLINE_MISS
    engine.step(reset=True)
    assert engine.step(event(1)).accepted


def test_far_future_and_sparse():
    engine = TemporalEngine()
    assert engine.step(event(0xFFFFFFFF)).accepted
    engine.run(10000)
    assert not engine.trace and len(engine.queue) == 1
    engine.reset()
    engine.step(event(3000))
    engine.run(3001)
    assert engine.trace == [(3000, GPIOState(1))]


def test_exhaustive_short_request_streams():
    # All 8^4 request streams at small width/depth. Assert independent invariants.
    for times in product(range(8), repeat=4):
        engine = TemporalEngine(depth=2, time_w=3)
        accepted = []
        for timestamp in times:
            result = engine.step(event(timestamp), drop=True)
            if result.accepted:
                assert timestamp > result.time
                assert not accepted or timestamp > accepted[-1]
                accepted.append(timestamp)
        engine.run(5)
        assert [t for t, _ in engine.trace] == accepted
        assert engine.epoch_closed and not engine.queue.contents


def test_producer_workload_independence():
    traces = []
    for mode in range(3):
        engine = TemporalEngine()
        for time in (20, 30, 50, 51):
            engine.step(event(time, time))
        while engine.time <= 55:
            # invalid/unrelated producer work cannot change accepted events
            engine.step(event(0) if mode and (mode == 1 or engine.time % 3 == 0) else None)
        traces.append(engine.trace)
    assert traces[0] == traces[1] == traces[2]


@pytest.mark.parametrize("invalid", [-1, 256])
def test_invalid_gpio(invalid):
    with pytest.raises(ValueError):
        GPIOState(invalid)


def test_invalid_parameters_and_width():
    with pytest.raises(ValueError):
        TemporalEngine(depth=0)
    with pytest.raises(ValueError):
        TemporalEngine(time_w=0)
    with pytest.raises(ValueError):
        TemporalEngine(time_w=3).step(event(8))
