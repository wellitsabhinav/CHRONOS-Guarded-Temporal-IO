from model.programmable_core import ProgrammableCore, ReclaimingEngine, Action, encode


def load(core, words):
    for i, word in enumerate(words):
        core.step(write=(i, word))
    core.step(start=True)
    return core.origin


def slice_program(deadline=30, sample=29, direct=False):
    return [encode(1, 0x0f3355), encode(1, (1 << 24) | 0xf0ccaa),
            encode(7, 0x0101), encode(4), encode(9 if direct else 3, deadline),
            encode(5, sample | ((1 << 26) if direct else 0)), encode(0)]


def test_first_slice_and_direct_tie():
    for direct in (False, True):
        for value in (0, 1):
            c = ProgrammableCore(guards=True)
            origin = load(c, slice_program(direct=direct))
            trace = []
            for _ in range(35):
                t = c.engine.time
                c.step(value)
                if c.engine.pulses['executed']:
                    trace.append((t-origin, c.engine.gpio))
            assert trace == [(30, 0xf0ccaa if value else 0x0f3355)]
            assert not c.faults and c.halted and c.sampler is None


def test_reuse_512_no_reset():
    for gen_w in (2, 8):
        c = ProgrammableCore(gen_w=gen_w, guards=True)
        load(c, slice_program(12, 11))
        for iteration in range(512):
            while not c.ready:
                c.step(iteration & 1)
            assert not c.faults
            assert c.engine.predicates[0].refs == 0
            assert c.engine.predicates[0].generation == iteration % c.engine.genmax + 1
            if iteration != 511:
                c.step(start=True)


def test_reclaim_conflicts_and_refcounts():
    e = ReclaimingEngine(depth=1, gen_w=2)
    e.step(command=(0, 1, True, False))
    e.step(Action(4, 1, 2, True, 0, 1))
    e.step(command=(0, 2, True, False))
    assert e.pulses['predicate_rejected'] and e.predicates[0].refs == 1
    e.step(command=(0, 1, False, True))
    e.step(Action(8, 3, 4, True, 0, 1), command=(0, 2, True, False))
    assert e.pulses['accepted'] and e.pulses['executed'] and e.predicates[0].refs == 1
    assert e.pulses['predicate_rejected']
    while e.time < 8:
        e.step()
    e.step(command=(0, 2, True, False))
    assert e.pulses['predicate_rejected'] and e.predicates[0].refs == 0
    e.step(command=(0, 2, True, False))
    assert e.pulses['predicate_accepted']
    e.step(command=(0, 1, False, True))
    assert e.pulses['predicate_rejected'] and not e.predicates[0].resolved


def test_pending_sampler_blocks_rearm_and_reset():
    c = ProgrammableCore()
    load(c, [encode(4), encode(5, 20), encode(4), encode(0)])
    for _ in range(8):
        c.step()
    assert c.stalled and c.engine.predicates[0].generation == 1
    c.step(reset=True)
    assert c.ready and not any(c.valid) and not c.faults and c.engine.gpio == 0


def test_bad_program_and_disabled_guards():
    for word in (encode(15), encode(0, 1), encode(4, 8)):
        c = ProgrammableCore()
        load(c, [word])
        c.step()
        assert c.halted and c.faults & 32
    c = ProgrammableCore(guards=False)
    load(c, slice_program())
    for _ in range(6):
        c.step()
    assert c.faults & 32 and not c.engine.queue
