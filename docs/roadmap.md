# Roadmap and qualification gates

| Milestone | Qualification label | Gate |
| --- | --- | --- |
| M0 temporal decoupling | CHRONOS_M0_TEMPORAL_DECOUPLING_CONFIRMED | Model, ordered FIFO/dispatcher, loadable top, faults/reset, differential evidence and physical checkpoint |
| M1 guarded futures | CHRONOS_M1_GUARDED_FUTURES_CONFIRMED | Predicates, guarded actions, false-event retirement, deterministic late resolution, no wrong-path external action |
| M2 programmable core | CHRONOS_M2_PROGRAMMABLE_CORE | Minimal processor, compact ISA, assembler, program storage, scheduling instructions and loader |
| M3 protocol set | CHRONOS_M3_PROTOCOL_SET_COMPLETE | Firmware UART, SPI and I2C on the same programmable architecture |
| M4 physical qualification | CHRONOS_M4_PHYSICAL_QUALIFIED | 6x4 GDS, timing, precheck, DRC, LVS as supplied, routed gate tests and submission-quality documentation |

Current classification is maintained in README and results. A logic pass
with unavailable physical hardening is
`CHRONOS_M0_LOGIC_VERIFIED_PHYSICAL_PENDING`; missing correctness evidence
is `CHRONOS_M0_INCOMPLETE`. Tool blockages are named explicitly rather than
converted into success. Full formal induction remains future qualification.

## Next exact objective: CHRONOS_M1_GUARDED_FUTURES

Investigate `A@T if P0=0` versus `B@T if P0=1`. Define the resolution margin,
GUARD_MISS behavior, false retirement, same-time alternatives and output
commit rule **before** RTL. A small predicate table could contain resolved
and value bits, but no implementation is committed by M0.

| Alternative | Benefit | Cost/question |
| --- | --- | --- |
| Individual guarded entries with early retirement | Simple head-based processing | Equal timestamps and false-entry retirement can consume dispatch bandwidth |
| Alternative bundle | One atomic choice per deadline | Wider entries; how many choices and pin states? |
| One-predicate conditional event | Small bounded selector | Restricts nesting/composition |
| Compiler merging | Smaller hardware representation | Must prove merged waveforms and margins equivalent |

Compare these against vendor timed/conditional ports and literature.
Require predicate resolution before a specified commit margin; do not
retime a late choice. Avoid queue-wide CAM/cancellation unless measurements
show it is necessary. CPU/ISA decisions follow M1, not this M0 run.
Stretch protocols and acceleration follow a healthy M4 only.
