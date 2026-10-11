# M0 verification checkpoint

Recorded 2026-10-11. Logical result: **PASS** for
`CHRONOS_M0_TEMPORAL_DECOUPLING`. Overall classification also depends on the
[physical checkpoint](m0_physical.md). This establishes the written M0
contract, not guarded speculation, protocol completeness or silicon results.

## Reproduction and provenance

From a clean checkout with the tools described in
[development_setup.md](../development_setup.md):

```sh
make test
make formal
CHRONOS_LIBERTY=/path/to/official/sg13cmos5l_stdcell_typ_1p20V_25C.lib make synth
python -m model.cli examples/m0/basic.json
```

The final local invocation was `make PYTHON=.venv/Scripts/python.exe test
formal synth`, with the documented native Windows tool environment
overrides. Python 3.12.5, pytest 8.4.2, cocotb 2.0.1, Icarus 12.0 (devel),
Verilator 5.020, and Yosys 0.30+48 (`b5b0b7e83`) were used.
The native cocotb embedding log identifies a compatible Python 3.12.4 DLL;
the command-line interpreter identifies 3.12.5. Linux CI is an independent
execution environment. No tool source patch was applied.

Production RTL hashes are recorded in [m0_synthesis.json](m0_synthesis.json).
RTL at CI commit `98dff4f2b9f9350ab1fc403a924c0ff4fc0f884d` is identical
after LF normalization. The later regressions add deliberate late-head
corruption and explicit atomic GPIO pattern coverage, without changing production RTL.

## Results

| Layer | Evidence |
| --- | --- |
| Python model | 35/35 pytest cases pass; one case explores all 4096 four-request timestamp streams at TIME_W=3/DEPTH=2 |
| Core RTL | Six cocotb suites × four configurations = 24/24 cases pass |
| Top-pin RTL | Four/four black-box integration suites pass |
| Differential | 48,000 randomized cycles compared; 15,851 accepted and 14,389 executed events |
| Lint | Verilator `--Wall` and Yosys structural `check -assert` pass |
| Formal | 24-edge bounded SAT pass at TIME_W=4, DEPTH=3, GPIO_W=3 |
| Standalone mapping | PASS; physical scope documented separately |

Verilator's filename warning alone is disabled because the inherited
`project.v` contains the required `tt_um_chronos` module. Other diagnostics
remain fatal. Simulator JUnit failures are checked even when vvp exits zero.

The final [PR M0 CI run](https://github.com/wellitsabhinav/CHRONOS-Guarded-Temporal-IO/actions/runs/38149832640)
passed all 35 model cases, 24 core cases, four top cases, lint and formal
checks on Linux at `5d267037ffa8a662856ce45b011c14e9a09044d4`, including
the late-head and GPIO-pattern regressions. The retained
[top-pin test workflow](https://github.com/wellitsabhinav/CHRONOS-Guarded-Temporal-IO/actions/runs/38149762397)
and [documentation workflow](https://github.com/wellitsabhinav/CHRONOS-Guarded-Temporal-IO/actions/runs/38149762450)
also passed at that commit. Earlier [M0 qualification](https://github.com/wellitsabhinav/CHRONOS-Guarded-Temporal-IO/actions/runs/38148339400)
at `98dff4f` covered the same production RTL before those additional tests.

## Meaningful random activity

Each configuration ran seeds **192, 193, 194, 195**, 3000 cycles per seed.
Full per-seed counts are in [m0_differential.json](m0_differential.json).
Compared state includes pre-edge ready, post-edge time/occupancy, all
24 GPIO bits, sticky faults, epoch state and accepted/rejected/executed
pulses. Reset flushing and still-pending events explain the difference
between admission and execution totals.

| TIME_W / DEPTH | Compared random cycles | Accepted | Executed |
| --- | ---: | ---: | ---: |
| 32 / 8 | 12,000 | 5,247 | 4,399 |
| 8 / 1 | 12,000 | 3,246 | 3,131 |
| 8 / 3 | 12,000 | 4,491 | 4,161 |
| 4 / 8 | 12,000 | 2,867 | 2,698 |

## Temporal and adversarial evidence

The core canonical trace remains exactly **20, 30, 50, 51** with an idle
producer, continuous invalid unrelated activity, or random stalls after
preloading. Every edge is checked against the independent deque model.
The real-pin loader needs 15 clocks per event; its corresponding trace is
**100, 110, 150, 151**, unchanged by subsequent staging/clear/idle commands.

Directed tests exercise empty/single/full queues, legal backpressure,
abandonment overflow, simultaneous full pop/refill, repeated pointer wrap,
DEPTH=1 and non-power-of-two DEPTH=3, one-event-per-clock dispatch/refill,
3000-clock gaps, far-future requests, now/past/equal/order faults, sticky
fault persistence without disturbing accepted events, and full/reset/reload
boundaries before/on/after dispatch. Reduced widths cover complete timer
epochs and post-wrap rejection. Atomic data/OE changes, disabled OE,
snapshot coherence, readback and deselection are checked through the pins.

A separate model test and VPI storage-corruption RTL test make a late
head deliberately. Both require discard + DEADLINE_MISS with no GPIO
change. Legal admission cannot create that state; there is no production
test hook or extra silicon port.

## Formal scope and findings

The reduced-parameter proof permits arbitrary producer valid/drop/payload
and later reset values, after an assumed first reset edge. It checks reset
safety, bounded occupancy/pointers, due-only nonempty dispatch, immutable
stored payloads, output-change causes, strictly ordered admission and
ordered head retirement. Padded unused memory-mux inputs are unconstrained;
actual addresses and the symbolic observed slot are asserted/assumed within
range. This is bounded safety evidence, not unbounded liveness or a
full-width proof. Summary: [m0_formal.json](m0_formal.json).

No model/RTL semantic disagreement remained in directed or random tests.
Bring-up found tooling integration issues: native helper paths with spaces,
mapped-cell structural checking before loading Liberty definitions, and
undefined padded memory-mux inputs in the formal harness. Documented
environment overrides, correct library loading, and explicit unconstrained
padding resolved them. None required changing M0 semantics or weakening
an architectural assertion.

## Limits

Verification does not establish novelty, electrical open-drain correctness,
analog setup/hold at pads, clock jitter tolerance, or fabricated behavior.
Exact output timing assumes continuous clock/selection, normal output mode
and no reset. Cross-epoch scheduling, guards, CPU, input capture and protocol
firmware remain later work. See the [normative semantics](../temporal_semantics.md).
