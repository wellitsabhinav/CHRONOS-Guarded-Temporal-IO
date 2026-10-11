"""Small M1 falsification suite: every architectural output per edge."""
import json
import os
from pathlib import Path
import random
import cocotb
from cocotb.triggers import Timer
from model import Event, GPIOState
from model.guarded_engine import GuardedEngine, GuardedFuture, PredicateCommand


class Harness:
    def __init__(self, dut):
        self.dut = dut
        self.model = GuardedEngine(depth=int(os.environ["CHRONOS_DEPTH"]), time_w=8,
                                   pred_w=1, gen_w=2)
        self.compared = 0
        self.misses = self.guards = self.normal = self.commands = 0

    async def cycle(self, event=None, predicate=None, *, reset=False, drop=False):
        d, m = self.dut, self.model
        guarded = isinstance(event, GuardedFuture)
        inputs = dict(clk=0, rst_n=int(not reset), event_valid=int(event is not None),
                      event_drop=int(drop), event_timestamp=event.timestamp if event else 0,
                      event_state=(event.action_false if guarded else event.state).packed if event else 0,
                      event_state_true=event.action_true.packed if guarded else 0,
                      event_guarded=int(guarded), event_predicate=event.predicate_id if guarded else 0,
                      event_generation=event.generation if guarded else 0,
                      predicate_valid=int(predicate is not None), predicate_arm=int(predicate.arm) if predicate else 0,
                      predicate_value=int(predicate.value) if predicate else 0,
                      predicate_id=predicate.predicate_id if predicate else 0,
                      predicate_generation=predicate.generation if predicate else 0)
        for name, value in inputs.items():
            getattr(d, name).value = value
        await Timer(5, unit="ns")
        assert int(d.event_ready.value) == (0 if reset else int(m.ready))
        r = m.step(event, predicate=predicate, reset=reset, drop=drop)
        d.clk.value = 1
        await Timer(5, unit="ns")
        expected = dict(time_now=m.time, occupancy=len(m.queue), gpio_state=m.gpio.packed,
                        faults=int(m.faults), epoch_closed=int(m.epoch_closed))
        expected.update({name: int(getattr(r, name)) for name in (
            "accepted", "rejected", "executed", "normal_executed", "false_executed",
            "true_executed", "guard_missed", "predicate_accepted", "predicate_rejected")})
        for field in ["active", "resolved", "value"]:
            expected[f"predicate_{field}_state"] = sum(int(getattr(p, field)) << i for i, p in m.predicates.items())
        expected["predicate_generation_state"] = sum(p.generation << (i*2) for i, p in m.predicates.items())
        observed = {name: int(getattr(d, name).value) for name in expected}
        assert observed == expected, f"edge {r.time}: {observed}, expected {expected}"
        assert not (r.false_executed and r.true_executed)
        self.compared += 1
        self.misses += r.guard_missed
        self.guards += r.false_executed or r.true_executed
        self.normal += r.normal_executed
        self.commands += r.predicate_accepted
        return r


def future(t, generation=1, pid=0):
    return GuardedFuture(t, pid, generation, GPIOState(0x55, 0x33, 0x0F),
                         GPIOState(0xAA, 0xCC, 0xF0))


@cocotb.test()
async def deadline_sweep(dut):
    h = Harness(dut)
    rows = []
    for margin in [20, 10, 5, 2, 1, 0, -1, None]:
        for value in [False, True]:
            await h.cycle(reset=True)
            await h.cycle(future(100), PredicateCommand(0, 1, arm=True))
            pulses = []
            while h.model.time <= 103:
                command = PredicateCommand(0, 1, value=value) if margin is not None and h.model.time == 100-margin else None
                pulses.append(await h.cycle(predicate=command))
            success = margin is not None and margin >= 1
            assert [t for t, _ in h.model.trace] == ([100] if success else [])
            assert sum(r.executed for r in pulses) == int(success)
            assert sum(r.guard_missed for r in pulses) == int(not success)
            assert not h.model.queue
            rows.append(dict(margin=margin, value=int(value), executed_at=100 if success else None,
                             gpio=h.model.gpio.packed, guard_miss=not success))
    Path("late_resolution.json").write_text(json.dumps(rows, indent=2)+"\n")


@cocotb.test()
async def adversarial_lifecycle_queue_reset_wrap(dut):
    h = Harness(dut)
    await h.cycle(reset=True)
    await h.cycle(future(12), PredicateCommand(0, 1, arm=True))
    await h.cycle(predicate=PredicateCommand(0, 2, value=True))  # future resolution
    await h.cycle(predicate=PredicateCommand(0, 1, value=True))
    await h.cycle(predicate=PredicateCommand(0, 1, value=False))  # immutable
    await h.cycle(predicate=PredicateCommand(0, 2, arm=True))
    await h.cycle(predicate=PredicateCommand(0, 1))  # stale
    await h.cycle(predicate=PredicateCommand(0, 2, value=False))
    while h.model.time < 12:
        await h.cycle()
    r = await h.cycle(future(20, 2))
    assert r.guard_missed and r.accepted
    while h.model.time < 20:
        await h.cycle()
    r = await h.cycle(predicate=PredicateCommand(0, 3, arm=True))
    assert r.false_executed and r.predicate_accepted  # pre-edge old state
    await h.cycle(predicate=PredicateCommand(0, 0, arm=True))  # no wrap
    await h.cycle(predicate=PredicateCommand(0, 1, arm=True))
    for reset_at in [0, 1, 5, 9, 10, 11]:
        await h.cycle(reset=True)
        await h.cycle(future(10), PredicateCommand(0, 1, arm=True), reset=reset_at==0)
        for t in range(1, reset_at):
            await h.cycle(predicate=PredicateCommand(0, 1, value=True) if t==5 else None)
        await h.cycle(future(30), PredicateCommand(0, 1, value=True), reset=True)
    await h.cycle(reset=True)
    for i in range(h.model.depth):
        await h.cycle(future(15+i))
    await h.cycle(Event(30, GPIOState(7)))  # backpressure
    await h.cycle(Event(30, GPIOState(7)), drop=True)
    while h.model.time < 15:
        await h.cycle()
    r = await h.cycle(Event(30, GPIOState(7)))
    assert r.guard_missed and r.accepted and len(h.model.queue)==h.model.depth
    while h.model.time <= 31:
        await h.cycle()
    assert h.model.trace == [(30, GPIOState(7))]
    await h.cycle(reset=True)
    await h.cycle(future(255), PredicateCommand(0, 1, arm=True))
    while h.model.time < 254:
        await h.cycle()
    await h.cycle(predicate=PredicateCommand(0, 1, value=True))
    assert (await h.cycle()).true_executed
    assert h.model.epoch_closed
    await h.cycle(future(5), PredicateCommand(0, 2, arm=True))
    await h.cycle(reset=True)
    # Equal actions and generation zero still have unambiguous outcomes.
    same = GuardedFuture(3, 1, 1, GPIOState(7), GPIOState(7))
    await h.cycle(same, PredicateCommand(1, 1, arm=True))
    await h.cycle(predicate=PredicateCommand(1, 1, value=False))
    await h.cycle()
    assert (await h.cycle()).false_executed


@cocotb.test()
async def small_seeded_differential(dut):
    h = Harness(dut)
    rows = []
    for seed in [1101, 1102, 1103]:
        rng = random.Random(seed)
        await h.cycle(reset=True)
        for cycle in range(600):
            m = h.model
            event = predicate = None
            if rng.random() < .65:
                t = max(m.time+1, (m.last_accepted or 0)+1)+rng.randrange(5)
                if t>m.limit or rng.random()<.15:
                    t = rng.randrange(m.limit+1)
                event = (future(t, rng.randrange(4), rng.randrange(2)) if rng.random()<.7
                         else Event(t, GPIOState.unpack(rng.randrange(1<<24))))
            if rng.random() < .6:
                pid = rng.randrange(2)
                p = m.predicates[pid]
                arm = not p.active or p.resolved or rng.random()<.15
                gen = min(3, p.generation+1) if arm else p.generation
                if rng.random()<.15:
                    gen = rng.randrange(4)
                predicate = PredicateCommand(pid, gen, arm, bool(rng.randrange(2)))
            try:
                await h.cycle(event, predicate, reset=cycle%190==189 or rng.random()<.02,
                              drop=rng.random()<.15)
            except AssertionError as e:
                raise AssertionError(f"seed={seed} cycle={cycle}: {e}") from e
        rows.append(dict(seed=seed, cycles=600))
    assert h.misses and h.guards and h.normal and h.commands
    summary = dict(time_w=8, depth=h.model.depth, pred_w=1, gen_w=2, seeds=rows,
                   cycles=1800, guard_executes=h.guards, guard_misses=h.misses,
                   ordinary_executes=h.normal, predicate_accepts=h.commands)
    Path("guarded_differential.json").write_text(json.dumps(summary, indent=2)+"\n")
