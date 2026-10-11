# M3 ordinary SPI peer timing: A–N report

Recorded 2026-10-12. **CHRONOS_M3_TIMING_CONTRACT_ESTABLISHED_NO_BASELINE_ADVANTAGE**.
The ordinary core supports a bounded, coordinated SPI-like waveform. Its
timestamp precision is reproducible with a small ordinary relative-WAIT
responder. Stop CHRONOS architectural expansion on this evidence.

## A. Executive classification

Measured: all 160 candidate points have identical complete-response success
for CHRONOS and the relative-WAIT baseline (88 successful points each).
The simpler edge-reactive baseline succeeds at 98 points, including shorter
peer periods. These totals mix deliberate failures and conditional setup
requirements; they are not reliability probabilities.

The fastest tested CHRONOS period valid across the tested phase grid is
**8 internal clocks**, or **fclk/8**. A 6-clock period works only at the exact
ideal digital boundary; a 7-clock period has a half-clock phase window.
The edge-reactive baseline passes the full grid at 6 clocks, with setup
approaching zero. No silicon frequency follows from these normalized results.

## B. Repository / branch / PR state

M3 branch: `development/m3-ordinary-spi-peer-timing`.
[Draft PR #5](https://github.com/wellitsabhinav/CHRONOS-Guarded-Temporal-IO/pull/5)
targets main. Qualification of the earlier stack was checked before merging:

| PR | Tested head | Merge commit | Qualification |
| --- | --- | --- | --- |
| #3 M0 closure | 41dc87d | 92554de | GDS, precheck, routed pad suites, logic/docs |
| #2 M1 | 36c65ac | 1628e59 | All nine applicable checks green |
| #4 M2 | 4632d7d | 29bca6a | All six logic checks green; no M2 physical requirement |

Main `29bca6a` has exactly the frozen M2 tree
`129984c271260a89b45f22bf69522a111b3ea8f7`. M3 incorporates this ancestry.
Prior evidence URLs use immutable tested SHAs. Obsolete remote M0/M1/M2
branches can be removed once their commits are reachable from main.
The pre-existing M0 local repair checkout is retained for historical assets.
Inherited main publication runs still build the unchanged M0 top; they are
separate from M3. The M3 branch excludes automatic physical runs.

## C. Frozen architecture

Ancestor: `4632d7dec8c533090eff4a70dae565d1cba8b260`.
Production `src/*.v`, M2 model and workload helpers are unchanged, checked by
the runner and hashed in the manifest. GUARDS_ENABLED=0, TIME_W=32, GPIO_W=24,
DEPTH=8, PRED_W=2, GEN_W=8; 16 writable words, one sampler, one issue port.
No ISA change, new production hardware, larger FIFO or physical campaign.

The four-bit fixture is M2's direct ordinary path: two complete GPIO actions,
compare/select configuration, ARM, ADVANCE, direct SAMPLE, three inverted
REACTIVE_EVENT instructions and HALT. Shorter responses truncate the same
unrolled instruction sequence. The command selects response 0x6 or 0x9.
MISO is uio_out[0]; its OE is uio_oe[0]. MOSI/SCK/CS are input bits 1/2/3.

## D. External peer model

`model/m3_peer.py` independently schedules raw CS/MOSI/SCK and observations
at integer-picosecond instants. Internal Tclk=10,000 ps is a simulation scale.
The peer controls period, phase, initial offset, edge polarity, CS lead/release,
data, length, sampling aperture and required setup deadline. Late/missing and
extra edges, reset, and mismatched programmed/peer periods are explicit cases.
Production stimuli use only the real nibble-loader/top pins. Correctness
reads data **and OE** at the exact peer edge, not an execution/acceptance pulse.

Ordinary mode: selected command is a raw rising edge E; first response update
is a falling edge F0, followed by rising sample T0. Subsequent samples are one
peer period apart. Let Oi=D+i*p be the programmed clock-edge times and
F0=D+phi+offset. The selected command is E=F0-P/2 and Ti=F0+P/2+i*P.
P is the peer period; p is the programmed integer spacing, both expressed
in internal-clock units here. Only one command is sampled; later peer edges
do not resynchronize the timestamp program.

Input/clock ties use ideal digital capture. Sample/clock ties read the old pin
state before the internal edge. Neither convention proves a physical setup
aperture. A required setup sigma is checked against the last actual pin-state
transition, including OE, rather than a redundant same-value event commit.

## E. Fair baselines

| Baseline | Mechanism | Timing information |
| --- | --- | --- |
| Edge-reactive | Same two-stage synchronization, compare/actions/inversion sequence; first output immediately at R, subsequent outputs on synchronized falling edges | Peer edges, no timer/FIFO/timestamps |
| Relative-WAIT | Same pre-edge synchronized word; programmable first delay and spacing; decrement/reload WAIT counter and emit registered choice | Same START origin, D and p as CHRONOS; no global time/per-event timestamps/FIFO |

Both are implemented in test-only RTL and independent Python models. They
receive comparable full GPIO actions, select/compare fields and lengths.
The immediate baseline has no artificial branch/issue delay. It skips the
first falling command/response boundary, then advances bits. Synchronized
CS release cancels it and clears OE. Missing edges hold its current value.

Relative WAIT loads D-1 at START, emits at D, reloads p-1 and emits at D+i*p.
It requires the decision before the emission edge, exactly R<=O-1. Missing
that first emission fail-stops rather than replaying or emitting later bits.
It uses CS only for command selection, matching CHRONOS's lack of queued
transaction cancellation. START preserves prior GPIO/OE. This comparator
is warranted because CHRONOS's apparent setup advantage over edge reaction
also uses advance knowledge of the output schedule.

## F. Timing methodology

Coarse periods 16/8/4/2 located the transition; 5/6/7 refined it. Six phases
0, 0.0001, 0.25, 0.5, 0.75, 0.9999 clocks and both command values are checked.
Boundary witnesses use +/-1 ps around capture boundaries and the 7-clock
half-phase boundary. Further targeted cases vary start/sample offsets,
period mismatch, CS, polarity, lengths, required setup and restarts.

Define C(E)=ceil(E/Tclk)*Tclk. For a present, selected command after arming:

| Timestamp | Meaning | Nominal derivation |
| --- | --- | --- |
| E | Actual raw command edge | Independent peer stimulus |
| stage1 | First capture | C(E) |
| stage2 | Second register update | C(E)+Tclk |
| S | Pre-edge word usable by sampler | C(E)+2*Tclk |
| R | Comparison/decision | S for the armed rising-edge fixture |
| A | Direct ordinary admission | R, if legal and space available |
| O | Actual pin transition | Requested D+i*p if emitted; absent for redundant same-value commits |
| T | Peer sampling edge | Independently scheduled |

E→S is [2,3) clocks in the ideal model; S→R=0 and R→A=0 for direct mode.
A→first O must be at least one clock. Missing E has no fabricated frontend
latency. Admission is inapplicable to eventless/WAIT output paths. The CSV
records each timestamp, decomposition, sample and diagnostic. Four-bit 0x6/0x9
contains a repeated middle value: commit time and physical transition time
are deliberately separate. No early/off-schedule output assertion depends on
looking up a matching timestamp: actual emissions must form an ordered subset
of the independently intended schedule.

For the nominal P=8, phi=0.0001-clock witness, the measured/derived timeline is:

```text
raw E=36.0001 -> stage1=37 -> stage2 update=38 -> S=R=A=39
             -> first pin O=40 -> peer T=44.0001
```

Thus E→S=2.9999, S→R=0, R→A=0, A→O=1, E→O=3.9999,
O→T=4.0001 and E→T=8 clocks. All timestamps are relative to START.

## G. Peer-period results

Normal rising sampling, zero requested electrical setup beyond logical
correctness. Each row contains six phases times two values:

| Period / Tclk | CHRONOS pass | Edge-reactive pass | Relative-WAIT pass |
| --- | ---: | ---: | ---: |
| 2 | 0/12 | 0/12 | 0/12 |
| 4 | 0/12 | 0/12 | 0/12 |
| 5 | 0/12 | 6/12 | 0/12 |
| 6 | 2/12 | 12/12 | 2/12 |
| 7 | 8/12 | 12/12 | 8/12 |
| 8 | 12/12 | 12/12 | 12/12 |
| 16 | 12/12 | 12/12 | 12/12 |

At period 8 the worst observed pin setup is 4 clocks for CHRONOS/WAIT and
1.0001 clocks for edge reaction. A requested two-clock setup makes CHRONOS
beat edge reaction at period 8, but WAIT matches it. At period 10 all three
meet the two-clock setup in the tested phases. This eliminates the apparent
timestamp-specific advantage. Absolute requested-edge error is zero for
CHRONOS/WAIT; edge reaction has one clock of phase-induced output jitter.

## H. Phase results

Derived continuous phase measures differ from the deliberately uneven grid:

| Period | CHRONOS/WAIT phase condition, offset=0 | Derived phase measure |
| --- | --- | ---: |
| 6 | phi=0, ideal input/clock tie only | 0% |
| 7 | 0<=phi<=0.5 | 50% |
| >=8 | 0<=phi<1 | 100% within this coordinated phase window |

The equations, plus targeted boundary witnesses, justify these measures;
they are not exhaustive analog qualification. At period 6, reactive setup
approaches zero as phi approaches zero from above; its 1 ps tested minimum
is not an engineering recommendation. Requiring at least one full clock of
setup moves the reactive all-phase integer period to 8 as well.

## I. Adversarial results

| Case | Externally relevant result |
| --- | --- |
| R=O-1 / R=O | First legal direct output / rejected request, no late replay |
| First output missed, later response programmed | Later original timestamp still emits; whole transaction is not fail-closed |
| FIFO full at direct sample | One-shot drop, faults 65, rejected output never replayed |
| Missing/expired command | No complete response; sampler/program fault, unresolved result |
| Missing later falling edge | CHRONOS and WAIT continue the known schedule; edge-reactive loses sequence alignment |
| Extra subclock pulse | Particular pulse filtered in tested phase; no general extra-edge immunity claim |
| Unexpected CS release | CHRONOS/WAIT keep emitting and driving OE; reactive cancels within synchronization latency |
| Falling selected command | Frozen M2 rising sampler fails; polarity-configurable reactive baseline succeeds |
| Adjacent data/OE actions | Atomic full GPIO updates on successive scheduled clocks |
| Reset before/at/after response | Clears data/OE and pending state; no stale replay |
| Reduced timer wrap | Final legal edge executes, epoch closes; overflow rejected, reset required |

These are measured behavior and architectural limitations, not repaired bugs.
No M0/M1/M2 scientific evidence or source was changed.

## J. Externally observed correctness / validation

78 Python model tests and six M3 cocotb test results pass. The peer suite has
160 candidate points and 635 sampling instants per path (1,905 CSV records),
26,836 every-edge core/baseline comparisons including real loader operations.
Eight alternating no-reset transactions add 504 comparisons and 32 correct
bits per path. Sixteen focused safety/epoch cases add 794 cycle comparisons.
The separate eventless descriptor suite compares 1,267 edges.

The default peer suite observes actual M2 wrapper pins. Safety tests use the
public core GPIO port and wrapper byte projection at TIME_W=8/5, DEPTH=1;
they do not claim asynchronous pad qualification. Existing bounded M2 proofs
remain applicable to unchanged RTL; no new formal or physical campaign.

## K. Supported timing contract

For the tested finite program, continuous ena, normal output mode and an open
reset epoch, a sufficient ideal digital contract is:

1. Load the program before START, and arm the descriptor before the selected
   rising SCK command. MOSI and active-low CS must be captured coherently.
2. C(E)+2*Tclk <= O0-Tclk, with FIFO space at direct admission. Equivalently,
   E<=O0-3*Tclk for this clock-aligned O0; no same-edge decision forwarding.
3. For every bit, Oi+sigma<=Ti and conservatively Ti<O(i+1), including all
   later raw peer period/phase drift. Repeated equal bits can widen the actual
   stability interval, but this conservative contract does not rely on that.
4. For O0=D, p=P, F0=D+phi+offset, the command condition becomes
   P/2>=3*Tclk+phi+offset. P>=8*Tclk covers phi in [0,Tclk), offset=0;
   this is **not** arbitrary asynchronous transaction-start tolerance.
5. START/write require halted, empty FIFO and idle sampler before the edge.
   The last output of the D=16,p=8 fixture is +40; core restart can first be
   admitted at +41. The demonstrated common peer restart is +51, after the
   final sample +44 and synchronized CS release +51. It gives 4/51=0.07843
   bits/clock excluding initial loading. It is a supported interval, not an
   exhaustive minimum-throughput result.
6. Reset closes pending transaction state. CS deassertion alone does not cancel
   admitted CHRONOS events or clear its OE. A conventional shared-bus SPI slave
   contract requiring automatic tri-state on deselection is unsupported.

Late start offsets +1/+4 clocks fail in the period-8 nominal fixture. Earlier
offsets work within arming and sample-stability requirements. Outside the
window, response admission/expiry faults can occur and the peer can read stale
or partial bits. Do not treat sticky fault flags as automatic transaction abort.

## L. Baseline comparison

Measured zero jitter, larger setup than edge reaction and preparation/execution
decoupling are real output properties. All are matched by the ordinary WAIT
descriptor using the same available schedule. The reactive baseline handles
unknown later clock edges and CS cancellation better. No comparator-optimality,
area advantage, full asynchronous SPI mode set, or novelty claim is established.
The utility gate failed, so no further prior-art campaign was justified.

## M. GO / NO-GO

**NO-GO for further CHRONOS expansion or physical qualification.** Timestamping
does not provide a unique externally useful timing capability for this workload.
The narrow scheduled contract exists, but an ordinary counter/action mechanism
matches it while edge reaction offers a broader bit-only frequency envelope.
Preserve the negative result and frozen guard history; do not add features to
rescue either hypothesis.

## N. Next exact milestone

Proposed reframe: **EVENTLESS_CS_FRAMED_SPI_UTILITY_GATE**. One next experiment:
qualify the general eventless descriptor on repeated four-bit CS-framed
transactions with arbitrary CS/host-START alignment, P=8*Tclk and at least
one-clock setup. Judge data/OE only at the peer interface, including deselection
and rearming. This proposal does not authorize another CHRONOS feature or
physical campaign and has not been started.

## Reproduction and evidence

```sh
python -m pip install -r test/requirements.txt
python -m pytest model/tests -q
python scripts/m3_experiment.py
# equivalent: make m3-experiment
```

Python 3.11+ and Icarus/cocotb are required. Standard Linux needs no overrides;
native Windows helper-path configuration is described in
[development setup](development_setup.md). Full transient JSON/JUnit stays in
ignored `build/`. Committed evidence is
[sample metrics CSV](results/m3_peer_samples.csv) and
[summary, hashes and witnesses](results/m3_peer_timing.json).
The runner checks production-source immutability against the frozen ancestor.
The [preregistered gate](../research/m3_hypothesis.md) preceded experimentation.
