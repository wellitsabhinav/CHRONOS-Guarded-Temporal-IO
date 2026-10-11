# M2 programmability and falsification: A–N report

Recorded 2026-10-11. Curated evidence is adjacent in `m2_*.json`; raw runs,
waveforms, PDK and tools remain ignored. Reproduce with `make m2-test
m2-experiment m2-formal`, `CHRONOS_LIBERTY=<pinned-liberty> make m2-synth`,
then `python scripts/m2_evidence.py`. Python runners also work without Make.

## A. Executive classification

**CHRONOS_M2_GUARDS_NO_GO_ORDINARY_DEFAULT**. Programmability, sampled inputs
and safe token reclamation work in the tested scope. Guards fail the protocol
utility gate against an implemented fused ordinary baseline. Core, model and
pin wrapper default to guards disabled; parameter-selectable guarded code
remains for reproducibility. No M2 physical or silicon qualification is claimed.

## B. Branch / PR state

`development/m2-programmable-core` descends from refreshed M1 `36c65ac`.
The normative contract preceded RTL; the first end-to-end slice preceded
protocol experiments. M0 [PR #1](https://github.com/wellitsabhinav/CHRONOS-Guarded-Temporal-IO/pull/1)
merged with merge commit `cdab7ee` after head `7166d8b` GDS/precheck/four
unchanged routed pad suites and final artifact identity passed. Two subsequent
M0 evidence/viewer-policy commits are tracked in draft
[PR #3](https://github.com/wellitsabhinav/CHRONOS-Guarded-Temporal-IO/pull/3).
Its head `41dc87d` logic/docs pass; existing GDS run `38159013249` was running
at the checkpoint. Preserve that branch until closure merges.
M1 [PR #2](https://github.com/wellitsabhinav/CHRONOS-Guarded-Temporal-IO/pull/2)
targets `main`; head `36c65ac` logic passes and existing physical run
`38159129429` was running. These runs still build the qualified M0 top.
M2 [draft PR #4](https://github.com/wellitsabhinav/CHRONOS-Guarded-Temporal-IO/pull/4)
targets M1; current-head CI is reported in its PR
separately from local evidence. M2 pushes exclude automatic GDS. Official
action implementations/pins, production physical config and `info.yaml` remain.

## C. M2 architecture

Companion `chronos_programmable_core` composes an in-order sequencer,
`chronos_reclaiming_engine`, synchronized input comparison and one sampler.
Defaults: TIME_W=32, GPIO_W=24, DEPTH=8, four predicates, GEN_W=8.
State includes 16×32 writable words, validity, PC, origin/cursor, two complete
GPIO action registers and a descriptor. `tt_um_chronos_m2` is separately
loadable through real pins. The qualified top still instantiates M0.
No loops, branches, general registers, compiler or fixed UART/SPI engine.

## D. Predicate reclamation

Count every accepted guarded reference and every retirement, including misses;
retire/enqueue uses the net accepted change. ARM requires **pre-edge** zero
references and no sampler ownership, so final retirement enables reuse on the
following edge. Generation cycles 1…255…1; zero stays invalid. Only the in-order
issuer and drained sampler own tokens; no host generation-bearing RESOLVE API
exists. Refcounts alone cannot exclude arbitrarily delayed external tokens.
M2 requires ARM before admission and prevents invalidating live references,
stricter than M1's lifecycle while retaining output safety. Reset/epoch closure
clear references and ownership after final-edge dispatch. 512 no-reset uses
pass at default widths, with two eight-bit rollovers, plus frequent GEN_W=2
rollovers at depths one/three and an ordinary GEN_W=8 configuration.

## E. Programming model

Opcodes 0–9: HALT, ACTION, EVENT, GUARDED_EVENT, ARM, SAMPLE, software RESOLVE,
COMPARE_CONFIG, inverted REACTIVE_EVENT, ADVANCE. The
[normative contract](../m2_programmable_core.md) defines bits and zero padding.
One instruction retires per edge. Event target cursor+increment stays fixed
through stalls; acceptance alone advances cursor. Overflow, malformed/unwritten
fetch, slot-15 overrun or semantic rejection fault/halt issuance; admitted events
and pending sampling continue. Reactive events await registered resolution and
fault once their fixed target is unreachable. START/write require halted,
empty FIFO, idle sampler and open epoch. Loaded words survive drained restarts;
reset clears validity. Eight low-first nibble SHIFTs load a word; WRITE advances
address. Other commands clear/set address, START, capture/shift a 15-byte status
snapshot. A 10-word reaction takes 93 loader commands including setup/START;
14-word UART takes 129. A drained restart needs one START.

## F. Input resolution

Input stable before E enters stage one at E, reaches stage two after E+1 and
can be sampled at E+2. R compares pre-edge stage two with `(input & mask)==expected`
and registers word/resolution together; guarded dispatch eligibility is R+1.
Report two-clock frontend delay separately from sample-to-output margin.
Timed descriptors capture on the specified edge; edge descriptors use the first
selected synchronized rising edge through inclusive expiration. Creation never
samples. Expiration releases ownership and sets SAMPLER_FAULT. Sampler resolution
wins over software predicate commands; conflicting instructions stall.
Digital simulation does not establish analog metastability or routed timing.

## G. Protocol results

UART byte `0xa6`: idle at origin+10, start at +20, eight LSB-first bits spaced
four clocks, stop at +56. Core/model and public-pin traces pass: 14 words,
11 ordinary events, zero predicates.
SPI-like select/MOSI/SCK stimulus selects `0x9` or `0x6` on a synchronized
rising control edge. Four programmed falling-edge deadlines have spacings
2/4/8 clocks; a peer reads MISO on intervening raw rising edges. All paths,
both values and late/absent samples are checked. This is a programmed-edge
fixture, not a full asynchronous SPI slave or SPI mode set.
Adversarial complete data/OE alternatives sample at T−10/−5/−3/−2/−1/T/T+1
or never. **192** combined cases have no wrong-path output. Unresolved guarded
heads miss/retire; later originally scheduled actions may execute after resolution,
but a missed first bit invalidates the response. Observation through origin+72
rejects changed timestamps or replay. Full-response guard/direct success is
identical throughout the sweep. See [protocol evidence](m2_protocol_experiments.json).

## H. Reactive vs guarded comparison

| Same-core path | Minimum R→T | Minimum raw pin E→T |
|---|---:|---:|
| Guarded prepared alternatives | 1 clock | 3 clocks |
| Instruction-driven reactive ordinary | 2 clocks | 4 clocks |
| Fused sample-and-enqueue ordinary | 1 clock | 3 clocks |

The fused descriptor snapshots actions/deadline, gets event-port priority at R
and drops a missed request without retry. Later bits use inversion; all SPI
alternatives differ, so redundant branch/action reloads are absent. Guard/direct
both use 10 words and two predicate commands per response. At the closest
successful spacing-2 case, guarded admission is at edges 5–8 with occupancy 4;
fused admission is 39–42 with occupancy 2. Guards avoid 33 issuance-stall clocks
but gain no usable sequence slack or completed responses. Across 32 alternating
SPI restarts, **both take 1504 clocks**: 128 correct outputs, no faults,
0.0851 events/clock, including starts/drain but excluding initial loading.
Instruction-driven reaction has the same rate at its two-clock margin.

## I. Verification

Five M2 model tests pass; complete model regression is 70/70. **19** M2 cocotb
test/configuration results pass, including core comparison, real loader pins,
raw defensive dispatcher conflicts, wrap, reuse/arithmetic, protocols and rate
measurements. Seeds 2201–2203 × 600 cycles at guarded depths 1/3 plus ordinary
depth 3 total **5400** randomized compared cycles; no larger campaign.
Every edge compares PC/instruction/stalls, time/origin/cursor, all logical FIFO
fields through hierarchy, GPIO, predicates/generations/counts, synchronization,
sampler descriptor/config/actions, command outcomes, retire pulses and faults.
Directed cases cover pre-edge reuse, multiple references, full same/different-
predicate pop/refill, stale tokens, sampler/software conflicts, immutable actions,
inclusive expiry/select gating, late/unresolved samples, malformed programs,
halted pending work, simultaneous WRITE/START rejection, reset and epoch closure. Default 32-bit cursor overflow
and generation rollover are tested; timer wrap is exercised at reduced width.

Separate **20-edge Yosys SAT** proofs pass: dispatcher TIME_W=4/DEPTH=3 and
integrated TIME_W=5/DEPTH=2, both GPIO_W=2/PRED_W=1/GEN_W=2. Initial reset is
assumed; later reset/input/write/start and raw dispatcher commands are arbitrary.
Assertions cover ownership/conservation, FIFO bounds/reset, immutable actions,
due-only commits, wrong-path exclusion and retirement without replay. First
dispatcher attempt timed out; only formal observer indexing changed before
successful rerun. These are reduced bounded proofs without induction/full-width/
analog claims. Default/guard-enabled core and default wrapper `--Wall` lint,
plus mapped structural checks, pass. [Proof scope](m2_formal.json).

## J. Cost

Final paired Yosys 0.30+48/ABC mapping uses confirmed typical CMOS5L Liberty
SHA256 `34163f3e7de9f854afac57332ba06f1739b78e7ac35660a8a5ddd39c570124ad`,
identical default widths and observable core ports. Wrapper is the supported
ordinary configuration, measured separately. [Provenance](m2_synthesis.json).

| Design | Cells | Area µm² | Flops |
|---|---:|---:|---:|
| M0 core | 1989 | 47252.3436 | 557 |
| M1 core | 2882 | 74532.7548 | 889 |
| M2 guarded core | 7292 | 154782.3438 | 1768 |
| M2 ordinary core | 6131 | 130991.4018 | 1483 |
| M2 ordinary pin wrapper | 6951 | 145166.4018 | 1629 |

Guards add 1161 cells, 285 flops and 23790.9420 µm²; guarded M2 is 2.077× M1.
Logical queues use 448 bits ordinary and 728 guarded. M2 adds 512 program bits
+16 validity; predicate generations use 32, flags 12, guarded references 16.
Pre-optimization inferred memory includes a 448-bit constant decoder table.
Final implementation uses standard-cell flops/muxes, no SRAM macros.
Twice the supported wrapper area is **290332.8036 µm²**, below **541450.2 µm²**
(60% of 902417 µm²). Plausibility passes; >2× M1 growth lacks required guard
utility. No M2 routed-fit, fanout, STA or 50 MHz conclusion follows.

## K. Measured bottlenecks

One issue/dispatch port supports one event/clock bursts. A 16-word ordinary
program admits 14 events; guarded ARM/RESOLVE overhead leaves 13. Across 32
drained starts, ordinary executes 448/1088 clocks (**0.4118/clock**), guarded
416/1056 (**0.3939/clock**). Full pop/refill occurs 192/160 times with occupancy
8; stalls total 320/288. These finite programs use a fixed 20-clock lead and
exclude initial loading, not universal peak rates. A 15-ARM program sustains
480/544 (0.8824 commands/clock), with one-clock bursts. Alternating ARM/RESOLVE
gives 224 resolutions in 512 clocks (0.4375/clock). One sampler, 16 slots,
strict ordering and closed epochs constrain longer protocols. Reduced issue
stalls do not increase measured SPI completion rate. [Rates](m2_throughput.json).

## L. Novelty assessment

The [prior-art assessment](../research/prior_art.md) is limited; timed I/O and
programmable conditional selection overlap established designs. The narrow
tested contract is immutable full-GPIO alternatives, internal generation
ownership and fail-closed retirement. Matching ordinary utility undermines
the practical distinction hypothesized in M1. No competitor optimum, first
implementation, patentability or global-novelty conclusion is established.

## M. GO / NO-GO

**NO-GO for guard retention.** Safety/programmability pass within stated limits
and cost is provisionally plausible, but reactive protocol advantage is absent
and guarded core exceeds twice M1 area. Equal first-output margin, full-response
success and sustained protocol rate trigger the conservative stop condition.
Ordinary mode is supported; guard code remains experimental. Stop architectural
expansion and start no M2 physical campaign.

## N. Next exact milestone

**CHRONOS_M3_ORDINARY_SPI_PEER_TIMING**: qualify ordinary programmable response
against varying external peer clocks, with externally observed bits and an
explicit supported timing window. Establish that one protocol contract before
further ISA expansion or physical work.
