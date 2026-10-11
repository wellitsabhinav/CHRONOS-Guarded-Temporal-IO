"""Cycle comparison of test-only eventless RTL against independent descriptor model.

Compile test/m3_eventless.v as top m3_eventless, with this cocotb module.
This verifies baseline semantics; the M3 peer harness measures external timing.
"""
from dataclasses import asdict
import random

import cocotb
from cocotb.triggers import Timer

from model.m3_baseline import EventlessDescriptor, EventlessResponder


class Harness:
    def __init__(self, dut):
        self.d = dut
        self.m = EventlessResponder()
        self.cycles = 0

    async def cycle(self, gpio=0, *, start=False, reset=False, descriptor=None):
        d, m = self.d, self.m
        program = descriptor or m.program
        values = dict(clk=0, rst_n=not reset, gpio_in=gpio, start=start, **asdict(program))
        for name, value in values.items():
            getattr(d, name).value = int(value)
        await Timer(5, unit='ns')
        m.step(gpio, start=start, reset=reset, descriptor=program)
        d.clk.value = 1
        await Timer(5, unit='ns')
        expected = {field: int(getattr(m, field)) for field in (
            'gpio_state', 'armed', 'active', 'completed', 'bit_index',
            'sampled', 'emitted', 'cancelled', 'sample_word')}
        expected.update(sync1_state=m.sync1, sync2_state=m.sync2, previous_state=m.previous)
        observed = {field: int(getattr(d, field).value) for field in expected}
        assert observed == expected, (self.cycles, observed, expected)
        self.cycles += 1


@cocotb.test()
async def spi_boundary_selection_restart_and_reset(dut):
    h = Harness(dut)
    for value in (0, 1):
        await h.cycle(reset=True)
        for _ in range(3):
            await h.cycle(8)
        await h.cycle(8, start=True)
        for word in (12, 0, 4 | (value << 1)):
            for _ in range(3):
                await h.cycle(word)
        assert h.m.sampled and h.m.emitted and h.m.bit_index == 0
        observed = []
        for bit in range(4):
            for _ in range(3):
                await h.cycle(value << 1)
            assert h.m.bit_index == bit
            for _ in range(3):
                await h.cycle(4 | (value << 1))
            observed.append((h.m.gpio_state >> 8) & 1)
        assert observed == [value, value ^ 1, value ^ 1, value]
        assert h.m.completed
        for _ in range(3):
            await h.cycle(8)
        assert not h.m.gpio_state >> 16 and h.m.completed
        await h.cycle(0, start=True)
        assert h.m.gpio_state == 0 and h.m.armed and not h.m.completed
        for _ in range(3):
            await h.cycle(4)
        for _ in range(3):
            await h.cycle(12)
        assert h.m.cancelled and not h.m.gpio_state >> 16 and not h.m.active
        await h.cycle(255, reset=True)
        assert not h.m.gpio_state and not h.m.sync2


@cocotb.test()
async def programmable_descriptors_and_targeted_random_interruption(dut):
    h = Harness(dut)
    rng = random.Random(3307)
    await h.cycle(reset=True)
    counts = dict(sampled=0, emitted=0, cancelled=0, completed=0)
    for case in range(16):
        trigger_pin, emit_pin, select_pin = rng.sample(range(8), 3)
        mask = 1 << rng.randrange(8)
        desc = EventlessDescriptor(
            action0=rng.randrange(1 << 24), action1=rng.randrange(1 << 24),
            compare_config=mask | (mask << 8) | (1 << 16) | (trigger_pin << 17) |
                           (1 << 20) | (select_pin << 21),
            invert_sequence=rng.randrange(16), response_length=case % 4 + 1,
            trigger_rising=bool(case & 1), emit_pin=emit_pin,
            emit_rising=bool(case & 2), hold_first_emit=bool(case & 4))
        await h.cycle(start=True, descriptor=desc)
        # A few stable levels make selected edges observable through 2 FFs.
        for cycle in range(72):
            gpio = rng.randrange(256) if cycle % 4 == 0 else gpio
            await h.cycle(gpio, descriptor=desc,
                          start=cycle == 39, reset=cycle == 61 and case % 3 == 0)
            for field in counts:
                counts[field] += bool(getattr(h.m, field))
    assert all(counts.values()), counts
