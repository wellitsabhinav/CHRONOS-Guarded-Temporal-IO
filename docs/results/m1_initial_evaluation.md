# M1 initial guarded-future evaluation

Recorded 2026-10-11. Decision: **GO** at the initial logic viability gate.
Classification: **CHRONOS_M1_GUARDED_FUTURES_LOGIC_ESTABLISHED**.
This does not establish M1 routed timing, pad integration or protocol usefulness.

## Hypothesis and implemented slice

Preparing complete false/true GPIO actions in one timestamp slot removes
post-decision software branching/action construction from the deadline path.
The independent deque model and experimental Verilog core implement the
[normative contract](../m1_guarded_futures.md): registered resolution at
pre-edge T-1 is eligible at T, same-edge T resolution is too late, and
unresolved/generation-mismatched futures retire without changing GPIO.
The generation table is write-once per ARM, with no wrap before reset.
Ordinary M0 events retain their exact ordering and retirement semantics.
The competition top still instantiates M0; no CPU or protocols were added.

## Minimal falsification evidence

* 30 targeted model cases pass: late resolution, generations/reuse/no-wrap,
  reset, full miss retirement/refill, ordinary interaction and timer wrap.
* Six cocotb suite/configuration results pass at TIME_W=8, GPIO_W=24,
  DEPTH=1/3, PRED_W=1, GEN_W=2. Every edge compares time, occupancy, GPIO,
  faults, event accept/reject/execution/miss pulses, predicate accept/reject,
  and every architectural predicate state bit.
* Three seeds (1101–1103), 600 cycles each/configuration: **3600 randomized
  compared cycles**, plus directed cases. Both guard execution and guard
  misses occur; this is not a campaign of mostly idle cycles.
  [Counts](m1_differential.json) retain actual hits.
* 20-edge Yosys SAT passes with arbitrary event/resolver inputs, TIME_W=4,
  DEPTH=3, GPIO_W=2, PRED_W=1, GEN_W=2. Assertions cover wrong-path safety,
  mutual exclusion, due-only commits, deterministic misses, no late commit,
  generation state transitions, reset, FIFO bounds/ordering/immutability.
  [Proof summary](m1_formal.json): bounded reduced-instance evidence only.
* Verilator 5.020 `--lint-only --Wall` passes on the default M1 core;
  paired mapped synthesis includes `check -assert` on both cores.

Python 3.12.4, cocotb 2.0.1, Icarus 12.0; mapping/proof Yosys 0.30+48.
Linux CI repeats these targeted M1 checks. M0's historical verification is
not rerun locally; its production source is unchanged.

## Late-resolution experiment

One bundle is scheduled before the decision for T=100. The RTL sweep tests
both values, with distinguishable complete data/OE actions. GPIO starts zero.
The independent model experiment uses 0x55/0xAA for concise reporting.

| Resolution edge | P=0 | P=1 | GUARD_MISS |
| --- | --- | --- | --- |
| T-20 | 0x55 at T | 0xAA at T | 0 |
| T-10 | 0x55 at T | 0xAA at T | 0 |
| T-5 | 0x55 at T | 0xAA at T | 0 |
| T-2 | 0x55 at T | 0xAA at T | 0 |
| T-1 | 0x55 at T | 0xAA at T | 0 |
| T | hold zero | hold zero | 1 |
| T+1 | hold zero | hold zero | 1 |
| unresolved | hold zero | hold zero | 1 |

No wrong-path output, both-path execution or late replay was observed.
The RTL trace checks run through T+3, not just the commit edge.
[Model experiment and baseline](m1_experiment.json) are reproducible.

## One conventional conceptual baseline

Assume registered observation at R, a branch/select stage at R+1, and an
ordinary M0 enqueue at R+2. M0 requires its request to be strictly future;
therefore exact output at T needs T-R>=3. M1 needs T-R>=1 after resolver
acceptance. The observed model sequence agrees with this derivation: the
reactive sequence fails at T-2/T-1 while the guarded bundle succeeds.
Gain against this **specified conceptual sequence**: two clocks, 40 ns at
the assumed 50 MHz. No CPU/competitor implementation was benchmarked.
An optimized dedicated selector that issues at R can also need just one
clock; M1 is not universally faster. Future pad synchronization/CPU issue
cost is outside the measured resolver margin.

## Initial implementation cost

One paired standalone-core mapping; all ports remain observable. Same
TIME_W=32/DEPTH=8/GPIO_W=24, Yosys and pinned CMOS5L typical Liberty.
M1 uses four predicates/eight-bit generations. These numbers exclude the
M0 loader; compare cores to cores, not against the earlier 2542-cell top.

| Measurement | M0 core | M1 core | Delta |
| --- | ---: | ---: | ---: |
| Mapped cells | 1989 | 2882 | +893 (+44.9%) |
| Cell area (µm²) | 47252.3436 | 74532.7548 | +27280.4112 (+57.7%) |
| Mapped flops | 557 | 889 | +332 (+59.6%) |

[Exact tool/library/source hashes](m1_synthesis.json). The FIFO payload grows
from 56 to 91 bits per slot: 280 additional store bits across eight slots.
The remaining growth covers predicates, control and selection. No SRAM,
CAM, cancellation network or live-input combinational output path is used.
The M1 core occupies about 0.0745 mm² of summed cell area, not routed area.
This is structurally modest enough to retain, but a CPU/memory/loader and
hold/clock repair must still fit the competition budget. No M1 STA estimate
or full GDS result is claimed; no configuration sweep was launched.

## Differentiation and decision

The [focused primary-source comparison](../research/prior_art.md) supports
only a narrow distinction: an atomic pair of prepared complete actions,
registered generation-scoped late selection, exact timestamp commit and
deterministic fail-closed miss retirement. Timed I/O and conditional protocol
control already exist, including Loom's deadline latch. Uniqueness and
superiority to optimized vendor/competition designs remain unproven.

**GO:** coherent semantics, independent agreement, bounded wrong-path safety,
measured one-cycle resolution margin and manageable core mapping cost justify
retaining this small mechanism provisionally. Stop benchmarking now.
**Known limitations:** no M1 pad API/CPU/firmware, no M1 routed qualification,
finite generation budget (255 ARM operations/ID/reset), single-head throughput,
strict ordering and no cross-epoch scheduling. M2 must establish safe predicate
reclamation and useful scheduling/resolve throughput; if these obstruct
programmable protocols, simplify or remove guards promptly.

**Next exact milestone:** CHRONOS_M2_PROGRAMMABLE_CORE.

## Reproduce

```sh
python -m pytest model/tests/test_guarded.py -q
python scripts/run_sim.py guarded
python scripts/m1_formal.py
CHRONOS_LIBERTY=/path/to/pinned/typical.lib python scripts/m1_synth.py
python scripts/m1_experiment.py
verilator --lint-only --Wall --top-module chronos_guarded_engine src/chronos_guarded_engine.v
```

Native Windows overrides follow [development setup](../development_setup.md).
Raw simulator/formal/synthesis outputs stay in ignored build directories.
