"""Focused contract tests for the test-only eventless response descriptor."""
from dataclasses import replace

from model.m3_baseline import EventlessDescriptor, EventlessResponder


def settle(core, gpio, cycles=3):
    for _ in range(cycles):
        core.step(gpio)


def test_preedge_synchronizer_and_immediate_bit_zero():
    c = EventlessResponder()
    c.step(start=True)
    c.step(6)  # raw selected SCK rise, matching MOSI; E
    assert not c.sampled and c.sync1 == 6 and c.sync2 == 0
    c.step(6)  # stage 2 becomes usable after this edge; S
    assert not c.sampled and c.sync2 == 6 and c.previous == 0
    c.step(6)  # read pre-edge stage 2; R and O coincide
    assert c.sampled and c.emitted and c.sample_word == 6
    assert c.gpio_state == c.descriptor.action1 and c.bit_index == 0


def test_command_boundary_and_four_response_samples():
    for value in (0, 1):
        c = EventlessResponder()
        c.step(start=True)
        settle(c, (value << 1) | 4)
        observed = []
        emissions = [c.gpio_state]
        for bit in range(4):
            settle(c, value << 1)  # first fall holds bit 0, later falls advance
            if c.emitted:
                emissions.append(c.gpio_state)
            assert c.bit_index == bit
            # These are the four response rising sample edges after trigger.
            settle(c, (value << 1) | 4)
            observed.append((c.gpio_state >> 8) & 1)
            assert (c.gpio_state >> 16) & 1
        assert observed == [value, value ^ 1, value ^ 1, value]
        assert len(emissions) == 4 and c.completed and c.active
        settle(c, value << 1)
        assert not c.emitted and c.bit_index == 3  # extra edges cannot replay
        settle(c, 8)
        assert not c.active and c.completed and not (c.gpio_state >> 16)


def test_selected_trigger_cancellation_and_restart():
    c = EventlessResponder()
    settle(c, 8)
    c.step(8, start=True)  # arm before CS is selected
    settle(c, 12)
    assert c.armed and not c.sampled and c.gpio_state == 0
    settle(c, 0)
    settle(c, 4)
    assert c.active and c.gpio_state == c.descriptor.action0
    c.step(12)
    c.step(12)
    assert c.active and c.gpio_state >> 16
    c.step(12)
    assert c.cancelled and not c.active and not c.armed
    assert not c.completed and not c.gpio_state >> 16
    settle(c, 0)
    settle(c, 4)
    assert not c.emitted and not c.active  # canceled response requires start
    old_sync = c.sync2
    c.step(0, start=True)
    assert c.gpio_state == 0 and c.armed and c.previous == old_sync
    c.step(255, reset=True)
    assert c.sync1 == c.sync2 == c.previous == c.gpio_state == 0
    assert not c.armed and not c.active


def test_programmable_actions_edges_and_missing_emit():
    d = replace(EventlessDescriptor(), action0=0x13579b, action1=0x2468ac,
                response_length=3, invert_sequence=0b101, emit_pin=5,
                emit_rising=True, hold_first_emit=False)
    c = EventlessResponder(d)
    c.step(start=True)
    c.step(0, descriptor=replace(d, action1=0))  # not captured without start
    settle(c, 6)
    assert c.gpio_state == d.action0 and c.bit_index == 0
    settle(c, 6, 30)  # missing emit edge holds response; no private timeout
    assert not c.completed and c.gpio_state == d.action0
    settle(c, 38)
    assert c.bit_index == 1 and c.gpio_state == d.action1
    settle(c, 6)
    settle(c, 38)
    assert c.bit_index == 2 and c.gpio_state == d.action0 and c.completed
    d = replace(d, trigger_rising=False, response_length=1)
    c.step(6, start=True, descriptor=d)
    settle(c, 6)
    settle(c, 2)
    assert c.sampled and c.gpio_state == d.action0 and c.completed
