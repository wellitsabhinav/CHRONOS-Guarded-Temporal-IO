# M1 guarded futures: normative contract

Specification dated 2026-10-11. This is the **CURRENT IMPLEMENTATION contract**
for the experimental core, independent of the M0 pad loader. M0's
[pre-edge terminology and admission rules](temporal_semantics.md) apply.
The **WORKING HYPOTHESIS** is that preparing both possible actions allows
information to arrive later without moving the original output deadline.

## Atomic alternative bundle

An ordinary event contains `(timestamp, state)`. A guarded future contains
`(timestamp, predicate_id, generation, action_false, action_true)`.
Both alternatives occupy one FIFO slot. All accepted timestamps remain
strictly increasing, including across ordinary/guarded events and an empty
queue. Actions atomically replace all GPIO data and enables. There is one
head retirement per clock, no bypass, sorting, CAM, rollback or cancellation.

## Deadline and registered resolution

For deadline T, a successful RESOLVE sampled on the rising edge whose
**pre-edge** timer is T-1 updates the predicate registers after that edge.
Those registers are visible before edge T and may select one action at T.
A RESOLVE sampled at T is too late for that event. Dispatch always reads
the pre-edge predicate state; there is no same-edge resolver forwarding.
The margin is measured from resolver acceptance, not an asynchronous pad
transition. Synchronization and CPU/host issue latency must be added later.

At T, matching active, resolved predicate state commits exactly one action.
Unresolved, inactive or mismatched generation state retires the bundle,
holds GPIO, pulses `guard_missed`, and sets sticky fault bit 3 GUARD_MISS.
A missed future never executes later. No default false branch is chosen.
Even equal-valued alternatives produce exactly one execution pulse.
Unresolved speculation never escapes to externally visible pins.

## Predicate lifecycle and generations

Default: four entries (`PRED_W=2`), eight-bit generations (`GEN_W=8`).
Each has active, generation, resolved, value. Reset clears all entries.
One synchronous predicate command may be sampled per edge:

* ARM(id, generation): accept only the exact next generation (initially 1),
  with no unsigned wrap. Mark active and unresolved, clear value.
* RESOLVE(id, generation, value): accept only an active matching generation
  that has not resolved. Resolution is write-once for that generation.
* Invalid/stale/duplicate commands pulse `predicate_rejected`, set sticky
  fault bit 4 PREDICATE_FAULT, and leave predicate state unchanged.

Accepted commands pulse `predicate_accepted`. ARM invalidates an earlier
generation: its queued bundles subsequently miss. A same-edge ARM and old
generation commit uses old pre-edge state and may commit; the new generation
affects only following edges. Reuse is explicit; RESOLVE cannot allocate.
Queued futures may reference a generation before ARM, but it must be
active and resolved before their deadline. A future generation cannot
match an older one; an old resolution cannot satisfy the new generation.
Generation zero is never armed. After 255 ARM operations on one ID, reset
is required; no wrap/ABA alias is permitted. **PLANNED WORK:** M2 must
address safe reclamation or epoch budgeting before sustained protocols.
This deliberately bounded lifecycle is adequate for the M1 experiment.

## Ordering, reset and rollover

On an active edge: decide/retire the existing head using pre-edge state;
admit the event using pre-edge ordering/capacity; accept a predicate command
using pre-edge lifecycle state; increment time. Event and predicate ports
are independent. Full retirement/refill is allowed, including guard misses.
M0 faults 0..2 retain their meanings. Faults hold until reset and do not
stop unrelated legal events. A late head sets DEADLINE_MISS and never
executes; GUARD_MISS is specifically a due guarded head decision.
Synchronous reset overrides everything, disables all GPIO enables and
clears queue, predicate state, pulses, time, history and faults.
Timer rollover follows M0: the final due event may execute, the epoch then
closes and scheduling requires reset. Predicate commands after closure
are rejected with PREDICATE_FAULT. A command at the final edge is sampled
normally but cannot enable post-wrap execution.

## Evidence boundary

The experiment exposes a synchronous core API. The existing competition
top remains the qualified M0 loadable design until M2 connects a programmable
producer/resolver. No CPU, protocol firmware, asynchronous input capture,
M1 pad-loader protocol or M1 GDS qualification is claimed. A core synthesis
comparison must keep every input/output observable and use the same tools,
parameters and Liberty for both designs.
