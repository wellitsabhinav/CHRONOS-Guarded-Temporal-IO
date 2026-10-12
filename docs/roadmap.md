# Roadmap and qualification gates

**Closed after EVENTLESS_SPI_FRAMING_INSUFFICIENT.** The project is preserved
as a negative research result. There is no next architecture milestone or
physical campaign. Historical plans below document the decisions at the time;
they do not authorize continued implementation. See the
[final A–N report](eventless_cs_framed_spi_gate.md).

| Milestone | Qualification label | Gate |
| --- | --- | --- |
| M0 temporal decoupling | CHRONOS_M0_TEMPORAL_DECOUPLING_CONFIRMED | Model, ordered FIFO/dispatcher, loadable top, faults/reset, differential evidence and physical checkpoint |
| M1 guarded futures | CHRONOS_M1_GUARDED_FUTURES_LOGIC_ESTABLISHED | Alternative bundles, registered predicates/generations, deterministic misses, small differential/proof/synthesis evidence and late-decision experiment |
| M2 programmable core | CHRONOS_M2_GUARDS_NO_GO_ORDINARY_DEFAULT | 16-word sequencer, program loader, synchronized sampling, owned token reclamation; guard utility failed |
| M3 ordinary SPI peer timing | CHRONOS_M3_TIMING_CONTRACT_ESTABLISHED_NO_BASELINE_ADVANTAGE | Coordinated external sampling contract established; relative-WAIT baseline matches timestamps/setup |
| Final eventless reframe gate | EVENTLESS_SPI_FRAMING_INSUFFICIENT | Candidate is edge-reactive baseline; raw CS/OE ownership and automatic rearm fail |
| Further CHRONOS physical qualification | STOPPED_AT_M3_UTILITY_GATE | No new campaign justified by the measured negative result |

Current classification is maintained in README and results. A logic pass
with unavailable physical hardening is
`CHRONOS_M0_LOGIC_VERIFIED_PHYSICAL_PENDING`; missing correctness evidence
is `CHRONOS_M0_INCOMPLETE`. Tool blockages are named explicitly rather than
converted into success. Full formal induction was not performed; no new
qualification campaign is authorized by the archival disposition.

## M1 decision: GO at the initial logic gate

This section records historical M1 reasoning, superseded by M2/M3 NO-GO gates.

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

## M3 decision: timing contract, no baseline advantage

All 160 tested points have identical CHRONOS/relative-WAIT complete-response
success. The coordinated 8-clock all-tested-phase timing contract is real;
its zero jitter and four-clock worst setup are matched by ordinary relative
WAIT/action execution. Edge reaction reaches 6 clocks with setup approaching
zero. See [M3 evaluation](m3_ordinary_spi_peer_timing.md).

Stop architectural expansion and physical qualification. The final authorized
reframe experiment was EVENTLESS_CS_FRAMED_SPI_UTILITY_GATE: repeated four-bit
CS-framed responses at period 8 with one-clock setup and arbitrary CS/host
alignment. It is a proposal for the simpler general response mechanism, not
an automatically launched next CHRONOS milestone. It has now completed with
EVENTLESS_SPI_FRAMING_INSUFFICIENT, closing further architectural work.
