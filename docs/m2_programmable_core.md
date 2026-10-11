# M2 programmable temporal core: normative contract

Specification 2026-10-11. M2 is a falsification experiment, not a general CPU
or physical qualification. M0 pre-edge time, unsigned ordering, single-head
retirement, atomic GPIO and reset-epoch semantics apply. M1 remains intact.
The measured utility gate is NO-GO for guards: `GUARDS_ENABLED=0` is the
supported core/wrapper/model default. Set it to 1 only to reproduce the guarded
experiment; opcode 3 faults when disabled. Both ordinary reactive paths remain.

## State and ownership

Defaults: TIME_W=32, GPIO_W=24, DEPTH=8, PRED_W=2, GEN_W=8. A 16x32 writable
program store has per-word validity; reset clears validity, not storage.
The in-order sequencer has PC, origin, cursor, two GPIO action registers and
compare configuration. One sampler descriptor captures configuration, token,
deadline and (for direct mode) both alternatives. No external token API exists.
START at PC zero requires halted, empty FIFO, idle sampler and open epoch.
It captures pre-edge time as origin/cursor. Program writes have the same gate.
Simultaneous core WRITE/START requests reject both and set PROGRAM_FAULT.
Loaded words persist across START. One instruction retires per clock at most.
HALT stops issuance but does not stop time, queued events or pending sampling.
Unwritten fetch, malformed instruction, PC overflow and semantic rejection
set PROGRAM_FAULT and halt issuance. Accepted events remain valid.

## Encoding

Opcode is [31:28]; unused bits must be zero. All increments are unsigned.

| Hex | Operation | Operand bits |
|---|---|---|
| 0 | HALT | zero |
| 1 | ACTION | selector 24, GPIO 23:0 |
| 2 | EVENT | selector 24, increment 23:0 |
| 3 | GUARDED_EVENT | swap 26, predicate 25:24, increment 23:0 |
| 4 | ARM | predicate 1:0 |
| 5 | SAMPLE | direct 26, predicate 25:24, origin offset/timeout 23:0 |
| 6 | RESOLVE | value 2, predicate 1:0 |
| 7 | COMPARE_CONFIG | mask 7:0, expected 15:8, rising-edge mode 16, trigger pin 19:17, active-low select gate 20, select pin 23:21 |
| 8 | REACTIVE_EVENT | invert 26, predicate 25:24, increment 23:0 |
| 9 | ADVANCE | increment 27:0 |

EVENT, GUARDED_EVENT and REACTIVE_EVENT use cursor+increment, fixed throughout
backpressure; only successful enqueue advances cursor. ADVANCE changes cursor
without an event. Arithmetic overflow faults rather than wrapping a deadline.
ARM blocks until safe; reactive events block until resolved, and fault if their
unchanged target is no longer future. Invalid predicate use faults. Software
RESOLVE targets the current allocation; it cannot allocate or resolve twice.
No loops, branches, WAIT opcode, general registers or compiler are required.

## Reclamation and same-edge rules

Each predicate has active, generation, resolved, value and outstanding queue
reference count. Guarded admission requires the active matching allocation.
Increment only on acceptance; decrement on every guarded retirement, including
guard/deadline misses. ARM requires pre-edge count zero and no sampler ownership.
It cycles generation 1..255..1 (reduced widths use the same nonzero cycle),
clears resolution and value. The last retirement allows ARM on the next edge.

This is intentionally stricter than M1: no pre-ARM guarded insertion and no
invalidation of live references. Tokens cannot escape to the host. The sole
in-order producer cannot retain an old command across ARM, and the sampler
must drain before reuse. Refcounts alone do not establish this ABA guarantee.
An arbitrarily delayed external token identical after wrap is unsupported.

Retire+enqueue uses the net count change, including full pop/refill. Retire+
RESOLVE dispatches with old state; resolution never forwards. Hardware sampler
resolution wins the single predicate command port over software ARM/RESOLVE;
the software instruction stalls. Same-edge direct enqueue wins the event port;
the software event stalls. Reclaim+ARM is allowed when already quiescent before
the edge. Reset overrides all operations. Timer closure clears queue references
and sampler ownership after any final due dispatch; later execution requires reset.

## Inputs and direct baseline

GPIO input continuously passes through two synchronization registers. Sampling
at edge R compares the pre-edge second-stage word: (input & mask)==expected.
The sampled word and predicate result are registered together. The result is
eligible for guarded dispatch at R+1, never R. Input stable before E enters the
first stage at E, second stage at E+1 and can be sampled at E+2. This digital
latency does not prove analog metastability behavior or routed timing.

SAMPLE requires active unresolved predicate and a future origin+offset. It
captures all descriptor fields, including generation; creation cannot sample.
Timed mode samples at that edge if selected. Edge mode samples the first rising
edge of the synchronized selected pin through the inclusive timeout. Expiration
without a selected sample clears ownership, sets SAMPLER_FAULT and leaves the
predicate unresolved. Reconfiguration never changes an existing descriptor.

Direct mode additionally captures the current cursor as output deadline and both
action registers. On sampling it selects and submits one ordinary event on that
same edge, with no artificial branch stage. Resolution is still registered.
Full queue or illegal direct admission records faults and discards the request;
there is no retry or late replay. A newly inserted event cannot dispatch that edge.
This baseline can tie the guarded one-clock sample-to-output margin.

## Faults, reset and observation

Fault bits 0..4 retain M0/M1 names. Bit 5 PROGRAM_FAULT identifies invalid
program/control requests; bit 6 SAMPLER_FAULT identifies failed capture/direct
issue. Faults are sticky until reset. Reset zeros GPIO/OE, predicates, counts,
sampler, synchronization, PC, action/config registers, origin/cursor and faults,
and starts halted. Storage validity prevents stale instruction/event execution.
Core status includes acceptance/rejection, retirement and predicate/sample pulses.
Differential tests additionally inspect logical queue contents and sampler state.

## Loadable experimental wrapper

The qualified tt_um_chronos and info.yaml remain M0. tt_um_chronos_m2 uses ui
nibbles/commands and uio inputs. ui[7] selects snapshot readback. ui[6:4]: 0 idle,
1 SHIFT (low nibble first), 2 WRITE then increment 4-bit address, 3 clear stage,
4 capture snapshot, 5 shift snapshot byte, 6 set address from nibble, 7 START.
Exactly eight SHIFTs are required per WRITE. Invalid writes consume staging and
set loader format fault; busy START/WRITE are rejected. Address wraps explicitly.
Snapshot bytes: status (halted, ready, epoch, sampler busy, accepted, executed,
sampled, loader format fault), faults, PC, occupancy, time[4], cursor[4], GPIO[3].
Capture observes pre-edge state. ena masks outputs and loader commands; core
time, sampling and dispatch continue. Exact pad visibility needs continuous
selection/clock, normal output mode and no reset, as in M0.

## Decision gate

Compare optimized instruction-driven and fused ordinary baselines with guarded
execution in the same core. Equal first-output latency is a tie. Retention needs
measured usable sequence slack or sustained deadline success on a reactive
protocol, plus safety, useful throughput and plausible cost. Synthetic success
alone is insufficient. Twice mapped wrapper area must fit 60% of the recorded
902417 square-micrometre floorplan; >2x M1 core growth requires clear protocol
benefit. Mapping is a plausibility screen, not physical qualification.
