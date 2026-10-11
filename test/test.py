"""Black-box top-pin tests, also used by the official routed gate workflow."""
import random
import cocotb
from cocotb.triggers import Timer
from model import Event, GPIOState, TemporalEngine


class Host:
    def __init__(self, dut):
        self.dut = dut
        self.model = TemporalEngine()
        self.nibbles = []
        self.format_fault = False
        self.snapshot = 0
        self.previous = (False, False, False)  # accepted, rejected, executed
        self.trace = []

    async def cycle(self, command=0, nibble=0, *, read=False, reset=False, ena=True):
        dut = self.dut
        dut.clk.value = 0
        dut.rst_n.value = int(not reset)
        dut.ena.value = int(ena)
        dut.ui_in.value = (int(read) << 7) | (command << 4) | nibble
        dut.uio_in.value = 0xA5  # unrelated input activity is allowed
        await Timer(5, unit="ns")
        request = None
        if reset:
            self.nibbles = []
            self.format_fault = False
            self.snapshot = 0
        elif ena:
            if command == 1:
                self.nibbles = (self.nibbles + [nibble])[-14:]
            elif command == 2:
                if len(self.nibbles) == 14:
                    word = sum(value << (4 * index) for index, value in enumerate(self.nibbles))
                    request = Event(word & 0xFFFFFFFF, GPIOState.unpack(word >> 32))
                else:
                    self.format_fault = True
                self.nibbles = []
            elif command == 3:
                self.nibbles = []
            elif command == 4:
                accepted, rejected, executed = self.previous
                status = (int(self.model.faults) | (int(self.format_fault) << 3)
                          | (int(self.model.epoch_closed) << 4) | (int(self.model.ready) << 5)
                          | (int(accepted) << 6) | (int(executed) << 7))
                queue = len(self.model.queue) | (int(rejected) << 4)
                self.snapshot = (status | (queue << 8) | (self.model.time << 16)
                                 | (self.model.gpio.packed << 48))
            elif command == 5:
                self.snapshot >>= 8
        result = self.model.step(request, drop=request is not None and not self.model.ready, reset=reset)
        self.previous = result.accepted, result.rejected, result.executed is not None
        dut.clk.value = 1
        await Timer(5, unit="ns")
        expected = (self.snapshot & 255 if read else self.model.gpio.uo,
                    self.model.gpio.uio_out, self.model.gpio.uio_oe) if ena else (0, 0, 0)
        observed = tuple(int(getattr(dut, name).value) for name in ("uo_out", "uio_out", "uio_oe"))
        assert observed == expected, f"top cycle {result.time} cmd={command}: {observed} != {expected}"
        if result.executed:
            self.trace.append((result.time, observed))
        return result

    async def load(self, timestamp, state):
        word = Event(timestamp, GPIOState.unpack(state)).word
        for index in range(14):
            await self.cycle(1, (word >> (index * 4)) & 15)
        return await self.cycle(2)

    async def idle(self, cycles):
        for _ in range(cycles):
            await self.cycle()

    async def capture(self):
        await self.cycle(4, read=True)
        values = [int(self.dut.uo_out.value)]
        for _ in range(8):
            await self.cycle(5, read=True)
            values.append(int(self.dut.uo_out.value))
        return values


@cocotb.test()
async def programmable_pin_trace_independent_of_loader_work(dut):
    traces = []
    for mode in range(3):
        host = Host(dut)
        await host.cycle(reset=True)
        for timestamp, state in [(100, 0x000055), (110, 0x0101AA), (150, 0x03020F), (151, 0x0704F0)]:
            assert (await host.load(timestamp, state)).accepted
        rng = random.Random(917)
        while host.model.time < 155:
            command = 0 if mode == 0 else (1 if mode == 1 else rng.choice([0, 1, 3, 6, 7]))
            await host.cycle(command, rng.randrange(16))
        assert host.trace == [(100, (85, 0, 0)), (110, (170, 1, 1)),
                              (150, (15, 2, 3)), (151, (240, 4, 7))]
        traces.append(host.trace)
    assert traces[0] == traces[1] == traces[2]


@cocotb.test()
async def loader_faults_full_queue_and_safe_reset(dut):
    host = Host(dut)
    await host.cycle(reset=True)
    await host.cycle(2)  # incomplete COMMIT
    assert (await host.capture())[0] & 8
    await host.cycle(reset=True)
    for index in range(8):
        assert (await host.load(500 + index * 10, 0xFFFFFF - index)).accepted
    assert not (await host.load(700, 0x123456)).accepted
    snap = await host.capture()
    assert snap[0] & 1 and snap[1] & 15 == 8
    await host.cycle(2, reset=True)
    await host.cycle(reset=True)
    snap = await host.capture()
    assert snap[0] & 31 == 0 and snap[1] == 0
    assert (await host.load(100, 0xAABBCC)).accepted
    assert (await host.load(99, 0xFFFFFF)).rejected
    assert (await host.load(host.model.time, 0xFFFFFF)).rejected
    snap = await host.capture()
    assert snap[0] & 6 == 6
    while host.model.time <= 101:
        await host.cycle()
    assert host.model.gpio.packed == 0xAABBCC


@cocotb.test()
async def reset_event_boundaries_readback_and_selection(dut):
    for boundary in [0, 1, 39, 40, 41]:
        host = Host(dut)
        await host.cycle(reset=True)
        if boundary:
            await host.load(40, 0xFFFFFF)
            while host.model.time < boundary:
                await host.cycle()
        await host.cycle(2, reset=True)
        assert (await host.load(40, 0x123456)).accepted
        while host.model.time < 40:
            await host.cycle()
        # Snapshot at execution captures the PRE-edge GPIO and timer.
        snap = await host.capture()
        assert int.from_bytes(bytes(snap[2:6]), "little") == 40
        assert snap[6:9] == [0, 0, 0]
        await host.cycle(ena=False)
        await host.cycle(2, ena=False)  # commands ignored while deselected
        await host.cycle()
        assert host.model.gpio.packed == 0x123456


@cocotb.test()
async def randomized_host_operations(dut):
    host = Host(dut)
    await host.cycle(reset=True)
    rng = random.Random(2026)
    for block in range(100):
        if block % 13 == 0:
            await host.cycle(reset=True)
        timestamp = max(host.model.time + 30, (host.model.last_accepted or 0) + 1)
        await host.load(timestamp, rng.randrange(1 << 24))
        for _ in range(rng.randrange(2, 20)):
            await host.cycle(rng.choice([0, 3, 4, 5, 6, 7]), rng.randrange(16), read=rng.random() < .3)
    await host.idle(100)
