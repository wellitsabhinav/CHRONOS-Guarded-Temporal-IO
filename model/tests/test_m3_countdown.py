"""Directed relative-WAIT competitor conventions and failure behavior."""
from dataclasses import replace

from model.m3_countdown import CountdownDescriptor, CountdownResponder


def test_exact_relative_wait_actions_for_early_or_last_legal_resolution():
    d = CountdownDescriptor(first_delay=10, spacing=3)
    for value in (0, 1):
        for decision in (1, 9):
            c = CountdownResponder(d)
            c.step(start=True)
            assert c.wait_count == 9 and not c.gpio_state
            trace = []
            for edge in range(1, 23):
                c.step((value << 1) | (4 if edge >= decision else 0))
                if c.sampled:
                    assert edge == decision
                if c.emitted:
                    trace.append((edge, (c.gpio_state >> 8) & 1))
            assert trace == [(10, value), (13, value ^ 1), (16, value ^ 1), (19, value)]
            assert c.completed and not c.active and c.faults == 0


def test_same_edge_resolution_or_missing_edge_fail_stops_without_replay():
    d = CountdownDescriptor(first_delay=5, spacing=2)
    for decision in (5, 6, None):
        c = CountdownResponder(d)
        c.gpio_state = 0x123456  # prior transaction remains driven
        c.step(start=True)
        for edge in range(1, 14):
            c.step(6 if decision is not None and edge >= decision else 2)
            assert not c.emitted and c.gpio_state == 0x123456
        assert c.faults == 1 and not c.active and not c.completed
        assert c.resolved == (decision == 5)  # R=O captured, but cannot rescue O
        c.step(start=True)
        assert c.faults == 1 and c.gpio_state == 0x123456 and c.active
        c.step(reset=True)
        assert c.faults == c.gpio_state == c.wait_count == c.previous == 0


def test_cs_gates_decision_and_preserves_prepared_sequence():
    c = CountdownResponder(CountdownDescriptor(first_delay=8, spacing=1))
    c.step(8, start=True)
    c.step(14)  # deselected rising edge cannot resolve
    assert not c.sampled and not c.resolved
    c.step(2)
    c.step(6)  # selected rising edge resolves
    assert c.sampled and c.resolved
    trace = []
    for edge in range(4, 12):
        c.step(14)  # CS high does not cancel programmed relative WAIT actions
        if c.emitted:
            trace.append(edge)
    assert trace == [8, 9, 10, 11] and c.completed and c.faults == 0
    assert c.gpio_state == 0x010100


def test_programmed_fields_capture_and_minimum_wait():
    d = CountdownDescriptor(action0=0x13579b, action1=0x2468ac,
                            first_delay=2, spacing=1, response_length=2,
                            invert_sequence=0b01)
    c = CountdownResponder(d)
    c.step(start=True)
    c.step(6, descriptor=replace(d, action0=0, action1=0))
    c.step(6)
    assert c.emitted and c.gpio_state == d.action0
    c.step(6)
    assert c.emitted and c.gpio_state == d.action1 and c.completed
    c.step(start=True, descriptor=replace(d, first_delay=1))
    c.step(0)
    assert c.faults == 1 and not c.active  # no post-START edge can resolve before O=1
