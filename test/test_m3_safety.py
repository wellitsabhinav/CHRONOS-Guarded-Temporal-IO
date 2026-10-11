"""Bounded M3 ordinary-core safety cases; architecture and model stay frozen.

Run this module with GUARDS_ENABLED=0, DEPTH=1, GEN_W=8, and TIME_W=8
for the response cases or TIME_W=5 for the epoch cases. The existing
Harness compares RTL/model on every edge. Additional assertions observe
the public gpio_state port after each edge; its three bytes are the data,
bidirectional data and OE mapped by tt_um_chronos_m2. These tests do not
exercise the wrapper loader or prove asynchronous/metastability behavior.
"""
import json
from pathlib import Path

import cocotb

from model.programmable_core import encode
from model.tests.test_programmable import slice_program
from test_programmable import Harness


FALSE_ACTION = 0x013355
TRUE_ACTION = 0x80CCAA
EDGE_SELECT_CONFIG = 1 | (1 << 8) | (1 << 16) | (2 << 17) | (1 << 20) | (3 << 21)


def pins(state):
    return dict(uo_data=state & 0xff, uio_data=(state >> 8) & 0xff,
                uio_oe=(state >> 16) & 0xff)


def executed(rows, origin):
    return [(r['time'] - origin, r['gpio']) for r in rows if r['executed']]


def output_edges(rows, origin):
    return [dict(O=r['time'] - origin, state=r['gpio'], **pins(r['gpio']))
            for r in rows if r['executed']]


def assert_outputs(rows, origin, expected):
    """Check full output state on every edge, not merely execution pulses."""
    assert executed(rows, origin) == expected
    state = 0
    by_time = dict(expected)
    for row in rows:
        state = by_time.get(row['time'] - origin, state)
        assert row['gpio'] == state, (row, state)


async def observe_until(h, absolute_last, gpio=1):
    start = len(h.rows)
    assert absolute_last <= h.m.engine.limit
    while h.m.engine.time <= absolute_last:
        t = h.m.engine.time
        await h.cycle(gpio(t) if callable(gpio) else gpio)
    return h.rows[start:]


async def response_safety(h):
    cases = []
    # The descriptor gets only one admission attempt at R. Full FIFO drops it;
    # the already admitted independent event still executes at its own O.
    await h.cycle(reset=True)
    words = [encode(1, FALSE_ACTION), encode(1, (1 << 24) | TRUE_ACTION),
             encode(7, 0x101), encode(2, 30), encode(4), encode(9, 5),
             encode(5, (1 << 26) | 15), encode(0)]
    origin = await h.load(words)
    rows = await observe_until(h, origin + 40)
    assert_outputs(rows, origin, [(30, FALSE_ACTION)])
    sampled = next(r for r in rows if r['sampled'])
    assert sampled['time'] == origin + 15 and sampled['occupancy'] == 1
    assert not sampled['accepted'] and not sampled['rejected']
    assert h.m.faults == 65 and h.m.sample_word == 1 and h.m.sampler is None
    cases.append(dict(case='direct_fifo_full', R=15, requested_O=35,
                      actual_outputs=output_edges(rows, origin), faults=h.m.faults,
                      response_dropped=True, no_replay_at_rejected_O=True))

    # Strict admission deadline: equality rejects; R=O-1 admits on R and
    # executes on O, with no early data/OE change or eventual late replay.
    for sample in (29, 30):
        await h.cycle(reset=True)
        origin = await h.load(slice_program(30, sample, True))
        rows = await observe_until(h, origin + 36)
        expected = [(30, 0xF0CCAA)] if sample == 29 else []
        assert_outputs(rows, origin, expected)
        sampled = next(r for r in rows if r['sampled'])
        assert sampled['time'] == origin + sample
        assert sampled['accepted'] == (sample == 29)
        assert sampled['rejected'] == (sample == 30)
        assert h.m.faults == (0 if sample == 29 else 68)
        cases.append(dict(case='minimum_direct_deadline' if sample == 29 else 'direct_deadline_passed',
                          R=sample, requested_O=30, admission_A=sample if sample == 29 else None,
                          actual_outputs=output_edges(rows, origin), faults=h.m.faults,
                          no_early_output=True, no_late_replay=True))

    # A missed first direct response is not transaction-wide cancellation.
    # Its predicate still resolves, so a later instruction can emit a
    # distinct response at its originally programmed later timestamp.
    await h.cycle(reset=True)
    words = [encode(1, FALSE_ACTION), encode(1, (1 << 24) | TRUE_ACTION),
             encode(7, 0x101), encode(4), encode(9, 20),
             encode(5, (1 << 26) | 20), encode(8, 5), encode(0)]
    origin = await h.load(words)
    rows = await observe_until(h, origin + 32)
    assert_outputs(rows, origin, [(25, TRUE_ACTION)])
    rejected = next(r for r in rows if r['rejected'])
    assert rejected['time'] == origin + 20 and rejected['sampled']
    assert h.m.faults == 68
    cases.append(dict(case='later_response_after_first_deadline_miss', R=20,
                      requested_outputs=[20, 25], rejected_O=20,
                      actual_outputs=output_edges(rows, origin), faults=h.m.faults,
                      no_replay_at_rejected_O=True,
                      limitation='A first response miss does not cancel later responses'))

    # Inclusive edge-sampler timeout. A raw rise at 18 is usable at 20;
    # a raw rise at 19 is usable at 21, after the descriptor has expired.
    for raw_rise in (None, 19, 18):
        await h.cycle(reset=True)
        words = [encode(1, FALSE_ACTION), encode(1, (1 << 24) | TRUE_ACTION),
                 encode(7, EDGE_SELECT_CONFIG), encode(4), encode(9, 30),
                 encode(5, (1 << 26) | 20), encode(0)]
        origin = await h.load(words)
        rows = await observe_until(h, origin + 36,
            lambda t: 1 | (4 if raw_rise is not None and t - origin >= raw_rise else 0))
        succeeded = raw_rise == 18
        assert_outputs(rows, origin, [(30, TRUE_ACTION)] if succeeded else [])
        assert [r['time'] - origin for r in rows if r['sampled']] == ([20] if succeeded else [])
        assert h.m.faults == (0 if succeeded else 64) and h.m.sampler is None
        cases.append(dict(case='sampler_missing_edge' if raw_rise is None else
                              ('sampler_late_edge' if raw_rise == 19 else 'sampler_inclusive_expiry_edge'),
                          E=raw_rise, S=None if raw_rise is None else raw_rise + 2,
                          R=20 if succeeded else None, sampler_expiration=20,
                          requested_O=30, actual_outputs=output_edges(rows, origin),
                          faults=h.m.faults))

    # Frozen limitation: CS qualifies capture, but deasserting it after the
    # sample/admission does not cancel an already scheduled response.
    await h.cycle(reset=True)
    origin = await h.load(words)
    rows = await observe_until(h, origin + 36,
        lambda t: 1 | (4 if t - origin >= 18 else 0) | (8 if t - origin >= 21 else 0))
    assert_outputs(rows, origin, [(30, TRUE_ACTION)])
    assert h.m.faults == 0
    cases.append(dict(case='cs_deassert_after_admission', E=18, R=20, admission_A=20,
                      raw_CS_deassertion=21, requested_O=30,
                      actual_outputs=output_edges(rows, origin), faults=0,
                      limitation='CS deassertion does not cancel queued responses'))

    # A depth-one FIFO can pop and admit at O, retaining adjacent timestamps
    # and simultaneous full data/OE transitions without an early response.
    await h.cycle(reset=True)
    words = [encode(1, 0x003355), encode(1, (1 << 24) | TRUE_ACTION),
             encode(2, (1 << 24) | 20), encode(2, 1), encode(0)]
    origin = await h.load(words)
    rows = await observe_until(h, origin + 26)
    assert_outputs(rows, origin, [(20, TRUE_ACTION), (21, 0x003355)])
    at_20 = next(r for r in rows if r['time'] == origin + 20)
    assert at_20['accepted'] and at_20['executed'] and at_20['occupancy'] == 1
    assert h.m.faults == 0 and any(r['stalled'] for r in rows)
    cases.append(dict(case='ordered_adjacent_data_and_oe', requested_outputs=[20, 21],
                      actual_outputs=output_edges(rows, origin), faults=0,
                      no_early_output=True, order_preserved=True))

    # Reset before resolution, while a response is queued, on its scheduled
    # edge, and after it emits. The old response cannot reappear after reset.
    for reset_at in (17, 19, 20, 21):
        await h.cycle(reset=True)
        origin = await h.load(slice_program(20, 18, True))
        rows = await observe_until(h, origin + reset_at - 1)
        assert_outputs(rows, origin, [(20, 0xF0CCAA)] if reset_at == 21 else [])
        await h.cycle(reset=True)
        assert h.m.engine.gpio == 0 and not h.m.engine.queue and h.m.sampler is None
        assert h.m.ready and not h.m.faults and not any(h.m.valid)
        after = await observe_until(h, origin + 24)
        assert all(r['gpio'] == 0 and not r['executed'] for r in after)
        cases.append(dict(case=f'reset_at_{reset_at}', reset_relative_to_origin=reset_at,
                          actual_outputs_before_reset=output_edges(rows, origin),
                          state_after_reset=pins(h.m.engine.gpio), no_replay_after_reset=True))
    return cases


async def epoch_safety(h):
    cases = []
    # An event at the final edge executes before the epoch closes. Afterwards
    # time wraps, while the epoch remains closed and admits no restart.
    await h.cycle(reset=True)
    origin = await h.load([encode(1, TRUE_ACTION), encode(2, 28), encode(0)])
    assert origin == 3 and origin + 28 == h.m.engine.limit == 31
    rows = []
    for _ in range(h.m.engine.limit - h.m.engine.time + 1):
        rows.append(await h.cycle())
    assert_outputs(rows, origin, [(28, TRUE_ACTION)])
    assert h.m.engine.time == 0 and h.m.engine.closed and not h.m.engine.queue
    assert not h.m.faults
    await h.cycle(start=True)
    assert not h.m.start_accepted
    after = [await h.cycle() for _ in range(35)]
    assert all(r['gpio'] == TRUE_ACTION and not r['executed'] and not r['accepted'] for r in after)
    assert h.m.engine.closed
    cases.append(dict(case='final_edge_then_closed_wrap', time_w=5, requested_O=31,
                      actual_outputs=[dict(O=31, state=TRUE_ACTION, **pins(TRUE_ACTION))],
                      wrap_replay=False, restart_accepted=False,
                      fault_after_invalid_restart=h.m.faults))

    # Overflow does not become a modular-time response in the next epoch.
    await h.cycle(reset=True)
    origin = await h.load([encode(1, TRUE_ACTION), encode(2, 29), encode(0)])
    rows = [await h.cycle() for _ in range(64)]
    assert not executed(rows, origin) and all(r['gpio'] == 0 for r in rows)
    assert h.m.faults == 36 and h.m.engine.closed and not h.m.engine.queue
    cases.append(dict(case='timestamp_overflow_no_modular_replay', requested_O=32,
                      actual_outputs=[], faults=h.m.faults, wrap_replay=False))

    # Reset is the operation that opens a fresh epoch and clears old output.
    await h.cycle(reset=True)
    origin = await h.load([encode(1, FALSE_ACTION), encode(2, 10), encode(0)])
    rows = await observe_until(h, origin + 15)
    assert_outputs(rows, origin, [(10, FALSE_ACTION)])
    assert h.m.ready and not h.m.engine.closed and not h.m.faults
    cases.append(dict(case='reset_opens_fresh_epoch', requested_O=origin + 10,
                      actual_outputs=[dict(O=origin + 10, state=FALSE_ACTION, **pins(FALSE_ACTION))],
                      faults=0))
    return cases


@cocotb.test()
async def directed_external_safety_cases(dut):
    h = Harness(dut)
    assert not h.guards and h.depth == 1 and h.gen_w == 8
    assert h.time_w in (5, 8)
    cases = await (epoch_safety(h) if h.time_w == 5 else response_safety(h))
    Path('m3_safety.json').write_text(json.dumps(dict(
        schema='chronos_m3_safety_v1', time_w=h.time_w, depth=h.depth,
        gen_w=h.gen_w, guards_enabled=h.guards,
        scope='bounded directed RTL/model comparison and public gpio_state observations',
        pin_projection='tt_um_chronos_m2 maps gpio[7:0], [15:8], [23:16] to data/data/OE',
        cases=cases, cycles=len(h.rows)), indent=2) + '\n')
