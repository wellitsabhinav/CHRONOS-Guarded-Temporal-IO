"""Cycle-level core differential tests against the independent behavioral model."""
import json
import os
from pathlib import Path
import random
import cocotb
from cocotb.triggers import Timer
from model import Event, GPIOState, TemporalEngine

SEEDS = [192, 193, 194, 195]


class Harness:
    def __init__(self, dut):
        self.dut = dut
        self.width = int(os.environ.get("CHRONOS_TIME_W", 32))
        self.depth = int(os.environ.get("CHRONOS_DEPTH", 8))
        self.model = TemporalEngine(self.depth, self.width)
        self.compared = 0
        self.accepts = self.executes = 0

    async def cycle(self, event=None, drop=False, reset=False):
        dut = self.dut
        dut.clk.value = 0
        dut.rst_n.value = int(not reset)
        dut.event_valid.value = int(event is not None)
        dut.event_drop.value = int(drop)
        dut.event_timestamp.value = event.timestamp if event else 0
        dut.event_state.value = event.state.packed if event else 0
        await Timer(5, unit="ns")
        assert int(dut.event_ready.value) == (0 if reset else int(self.model.ready))
        result = self.model.step(event, drop=drop, reset=reset)
        dut.clk.value = 1
        await Timer(5, unit="ns")
        observed = tuple(int(getattr(dut, name).value) for name in (
            "time_now", "occupancy", "gpio_state", "faults", "epoch_closed",
            "accepted", "rejected", "executed"))
        expected = (self.model.time, len(self.model.queue), self.model.gpio.packed,
                    int(self.model.faults), int(self.model.epoch_closed),
                    int(result.accepted), int(result.rejected), int(result.executed is not None))
        assert observed == expected, f"cycle {result.time}: got {observed}, expected {expected}"
        self.compared += 1
        self.accepts += result.accepted
        self.executes += result.executed is not None
        return result

    async def idle(self, count):
        for _ in range(count):
            await self.cycle()


def event(time, state=1):
    return Event(time, GPIOState.unpack(state))


@cocotb.test()
async def canonical_producer_independence(dut):
    harness = Harness(dut)
    await harness.cycle(reset=True)
    if harness.width < 8 or harness.depth < 4:
        assert (await harness.cycle(event(1, 0xFFFFFF))).accepted
        assert (await harness.cycle()).executed.state.packed == 0xFFFFFF
        return
    root = Path(__file__).resolve().parents[1]
    expected = json.loads((root / "examples/m0/basic.expected.json").read_text())
    traces = []
    for mode in range(3):
        await harness.cycle(reset=True)
        for row in expected:
            await harness.cycle(Event(row["cycle"], GPIOState(row["uo"], row["uio_out"], row["uio_oe"])))
        rng = random.Random(777)
        while harness.model.time <= 55:
            await harness.cycle(event(0) if mode == 1 or (mode == 2 and rng.randrange(3) == 0) else None)
        trace = [{"cycle": time, "uo": state.uo, "uio_out": state.uio_out,
                  "uio_oe": state.uio_oe} for time, state in harness.model.trace]
        assert trace == expected
        traces.append(trace)
    assert traces[0] == traces[1] == traces[2]


@cocotb.test()
async def queue_faults_dense_and_sparse(dut):
    h = Harness(dut)
    await h.cycle(reset=True)
    if h.width >= 8:
        start = h.depth + 5
        for i in range(h.depth):
            assert (await h.cycle(event(start + i, i + 1))).accepted
        assert len(h.model.queue) == h.depth
        # A stable valid request while waiting is legal, abandonment is visible.
        await h.cycle(event(start + h.depth + 10))
        assert h.model.faults == 0
        await h.cycle(event(start + h.depth + 10), drop=True)
        assert int(h.model.faults) == 1
        await h.idle(start - h.model.time)
        both = await h.cycle(event(start + h.depth + 10, 0xABCDEF))
        assert both.accepted and both.executed
        assert len(h.model.queue) == h.depth
        await h.idle(h.depth + 11)
        await h.cycle(event(h.model.time))
        assert int(h.model.faults) & 4
        await h.cycle(event(start))
        assert int(h.model.faults) & 2

    # Max core rate, repeated pointer wraps including depth one and depth three.
    for batch in range(10):
        await h.cycle(reset=True)
        count = min(h.model.limit - 1, 100)
        for i in range(count):
            result = await h.cycle(event(i + 1, ((batch + i) % 255) + 1))
            assert result.accepted
            if i:
                assert result.executed.timestamp == i
        await h.cycle()
        assert h.model.faults == 0
    if h.width == 32:
        await h.cycle(reset=True)
        await h.cycle(event(3000, 0x123456))
        await h.idle(3001)
        assert h.model.trace == [(3000, GPIOState.unpack(0x123456))]
        await h.cycle(reset=True)
        await h.cycle(event(0xFFFFFFFF))
        await h.idle(300)
        assert not h.model.trace


@cocotb.test()
async def reset_and_epoch_edges(dut):
    h = Harness(dut)
    await h.cycle(reset=True)
    target = min(12, h.model.limit)
    for boundary in [0, 1, target - 1, target, target + 1]:
        await h.cycle(reset=True)
        if boundary:
            await h.cycle(event(target, 0xFFFFFF))
            await h.idle(boundary - 1)
        await h.cycle(event(h.model.limit), reset=True)
        await h.cycle(reset=True)
        assert (await h.cycle(event(1, 0x123456))).accepted
        assert (await h.cycle()).executed.state.packed == 0x123456
    if h.width < 32:
        await h.cycle(reset=True)
        await h.cycle(event(h.model.limit, 0xAB1234))
        await h.idle(h.model.limit)
        assert h.model.epoch_closed and h.model.time == 0
        assert h.model.gpio.packed == 0xAB1234
        await h.idle(h.model.limit + 1)
        assert (await h.cycle(event(h.model.limit))).rejected
        await h.cycle(reset=True)
        assert (await h.cycle(event(1))).accepted
    # Reset while completely full and while presented with another request.
    await h.cycle(reset=True)
    base = h.depth
    for i in range(h.depth):
        await h.cycle(event(base + i, 0xFFFFFF))
    assert len(h.model.queue) == h.depth
    await h.cycle(event(h.model.limit), reset=True)
    assert h.model.gpio.packed == 0 and len(h.model.queue) == 0


@cocotb.test()
async def randomized_differential(dut):
    h = Harness(dut)
    per_seed = []
    for seed in SEEDS:
        rng = random.Random(seed)
        await h.cycle(reset=True)
        before = h.accepts, h.executes
        for cycle in range(3000):
            period = 400 if h.width >= 8 else 24
            reset = cycle % period == period - 1
            reset = reset or rng.randrange(101) == 0
            request = None
            if rng.random() < 0.7:
                if rng.random() < 0.72:
                    earliest = max(h.model.time + 1, (h.model.last_accepted or 0) + 1)
                    timestamp = earliest + rng.randrange(4)
                    if timestamp > h.model.limit:
                        timestamp = rng.randrange(h.model.limit + 1)
                else:
                    timestamp = rng.randrange(min(h.model.limit + 1, h.model.time + 12))
                request = event(timestamp, rng.randrange(1 << 24))
            try:
                await h.cycle(request, drop=rng.random() < 0.3, reset=reset)
            except AssertionError as error:
                raise AssertionError(f"seed={seed} stream_cycle={cycle}: {error}") from error
        per_seed.append({"seed": seed, "cycles": 3000, "accepted": h.accepts - before[0],
                         "executed": h.executes - before[1]})
    report = {"time_w": h.width, "depth": h.depth, "random_cycles": 12000,
              "seeds": per_seed}
    Path("differential_summary.json").write_text(json.dumps(report, indent=2) + "\n")
    dut._log.info("DIFFERENTIAL %s", json.dumps(report))
