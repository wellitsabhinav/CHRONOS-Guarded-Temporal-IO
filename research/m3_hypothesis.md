# M3 preregistered utility gate

Frozen on 2026-10-12 before the peer experiments. Ancestor:
`4632d7dec8c533090eff4a70dae565d1cba8b260` (qualified ordinary M2).
M2's `CHRONOS_M2_GUARDS_NO_GO_ORDINARY_DEFAULT` remains frozen.

Hypothesis: ordinary timestamp scheduling offers an externally useful timing
capability over a fair eventless programmable responder. Success is a larger
correct peer envelope, useful setup/deadline tolerance, lower observable jitter,
or useful fail-closed hard-deadline behavior. Internal stalls alone do not count.
Equal correctness with different early output times does not establish utility.

Freeze `src/*.v`, the ISA and M2 reference model. Use the default ordinary core:
TIME_W=32, GPIO_W=24, DEPTH=8, PRED_W=2, GEN_W=8, GUARDS_ENABLED=0;
16 program words, one sampler, one issue port, two input synchronization stages.
The default loadable M2 wrapper exposes data/OE and the real nibble loader.
Its 10-word M2 direct SPI fixture selects 0x6/0x9 and schedules four outputs.
Keep exact source hashes in the experiment manifest. No physical campaign.

The competitor receives the same raw pins through identical digital
synchronization and uses the same two actions and invert sequence. It emits
the first resolved action immediately, then reacts to synchronized peer falling
edges. It has no timestamps or FIFO, and no imposed branch/issue delay. This
test-only competitor does not extend CHRONOS hardware.

The external oracle reads data AND OE at each exact peer sampling instant.
Record raw E, stage-one capture, stage-two update, usable S, decision R,
admission A, output O, sampling T separately. Hierarchy is diagnostic only.
Search periods coarsely, refine the boundary, then test synchronization-adjacent
phases, start offsets, sampling offsets, restarts and protocol disruptions.
Model/RTL comparison supplements, never replaces, the pin oracle.

Decision labels are exactly:
`CHRONOS_M3_TIMING_ADVANTAGE_ESTABLISHED`,
`CHRONOS_M3_TIMING_CONTRACT_ESTABLISHED_NO_BASELINE_ADVANTAGE`,
`CHRONOS_M3_PROTOCOL_TIMING_INSUFFICIENT`, or
`CHRONOS_M3_INCONCLUSIVE` for a real unresolved blocker.
Do not patch a limitation to change the result. If a useful advantage survives,
do a focused prior-art check and propose only the smallest physical follow-up.
