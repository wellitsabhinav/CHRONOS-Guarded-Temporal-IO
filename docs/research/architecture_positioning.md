# Architecture positioning

## Established prior art

Timed GPIO, buffered output, deterministic I/O, deadline execution,
output compare, and explicit time in programming models are established.
XMOS timed buffered ports are especially close to M0. See [survey](prior_art.md).

## Current facts

M0 is an ordered queue of atomic future GPIO states with an independent
clock-driven dispatcher. Qualification results are reported separately.
There is no CPU, unresolved predicate, alternative future, or speculative
commit machinery. Neither simulation nor synthesis establishes novelty.

## Working hypothesis

Bounded guarded future waveforms may make control-dependent protocol
responses easier to schedule: prepare alternatives while a predicate is
unresolved, then select one before a defined commit margin without moving
its timestamp. A compact encoding may keep physical cost small.

## Unproven claims

Novelty of this combination, compiler usefulness, area efficiency,
comparison against xCORE conditional/timed I/O, and improved protocol
coverage are **unproven**. No "first", patentability or performance claim
is made. M0 validates temporal decoupling only.

## Deeper review still required

Investigate predicated/conditional timer peripherals, programmable waveform
sequencers, transactional external I/O, FPGA event engines, speculative
real-time execution, and patent claims. Determine whether predicates bind
individual states or bundles; define same-timestamp alternative retirement,
commit margin, late-resolution failure and ordering across canceled work.
Compare physical cost and accepted-to-executed timing against vendor designs.
