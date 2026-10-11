# Roadmap and qualification gates

| Milestone | Qualification label | Gate |
| --- | --- | --- |
| M0 temporal decoupling | CHRONOS_M0_TEMPORAL_DECOUPLING_CONFIRMED | Model, ordered FIFO/dispatcher, loadable top, faults/reset, differential evidence and physical checkpoint |
| M1 guarded futures | CHRONOS_M1_GUARDED_FUTURES_LOGIC_ESTABLISHED | Alternative bundles, registered predicates/generations, deterministic misses, small differential/proof/synthesis evidence and late-decision experiment |
| M2 programmable core | CHRONOS_M2_GUARDS_NO_GO_ORDINARY_DEFAULT | 16-word sequencer, program loader, synchronized sampling, owned token reclamation; guard utility failed |
| M3 protocol set | CHRONOS_M3_PROTOCOL_SET_COMPLETE | Firmware UART, SPI and I2C on the same programmable architecture |
| M4 physical qualification | CHRONOS_M4_PHYSICAL_QUALIFIED | 6x4 GDS, timing, precheck, DRC, LVS as supplied, routed gate tests and submission-quality documentation |

Current classification is maintained in README and results. A logic pass
with unavailable physical hardening is
`CHRONOS_M0_LOGIC_VERIFIED_PHYSICAL_PENDING`; missing correctness evidence
is `CHRONOS_M0_INCOMPLETE`. Tool blockages are named explicitly rather than
converted into success. Full formal induction remains future qualification.

## M1 decision: GO at the initial logic gate

**CURRENT IMPLEMENTATION:** one atomic alternative bundle, four predicates,
registered T-1 resolution, write-once generations, fail-closed GUARD_MISS.
See [initial evaluation](results/m1_initial_evaluation.md). The mechanism
survives the targeted tests, reduced bounded proof and paired synthesis.
Retain it provisionally and stop expanding the benchmark campaign.

| Alternative | Benefit | Cost/question |
| --- | --- | --- |
| Individual guarded entries with early retirement | Simple head-based processing | Equal timestamps and false-entry retirement can consume dispatch bandwidth |
| Alternative bundle | One atomic choice per deadline | Wider entries; how many choices and pin states? |
| One-predicate conditional event | Small bounded selector | Restricts nesting/composition |
| Compiler merging | Smaller hardware representation | Must prove merged waveforms and margins equivalent |

The alternatives table records design choices, not additional implementations.
**UNPROVEN CLAIM:** superiority to optimized PIO/PRU/XMOS/Loom implementations
or novelty across all prior art. **PLANNED WORK / next exact milestone:**
`CHRONOS_M2_PROGRAMMABLE_CORE`, with a compact producer/resolver API and safe
predicate reclamation. UART/SPI/I2C firmware belongs to M3. Do not freeze
an ISA or build protocol engines during M1. Expanded physical qualification
follows programmable integration, with the 6x4/50 MHz budget retained.

## M2 decision: ordinary default, NO-GO for guards

Fused ordinary sampling ties the guarded one-clock margin and full SPI-like
response success across the specified sweep. Both complete 32 responses in
1504 clocks. Guarded M2 costs 2.077× M1 core area without measured protocol
benefit. See [M2 evaluation](results/m2_initial_evaluation.md). Retain reproducible
guard experiments and stop that expansion. The sole next milestone is
**CHRONOS_M3_ORDINARY_SPI_PEER_TIMING**: qualify ordinary correctness against
varying external clocks. No M2 physical campaign starts on the negative result.
