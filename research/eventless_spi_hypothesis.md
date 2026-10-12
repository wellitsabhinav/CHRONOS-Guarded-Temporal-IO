# Preregistered EVENTLESS_CS_FRAMED_SPI_UTILITY_GATE

Frozen ancestor: df29e14cea7e13489e1b128a590f1f13c3e58681 (M3 merge).
M3 remains CHRONOS_M3_TIMING_CONTRACT_ESTABLISHED_NO_BASELINE_ADVANTAGE.
This gate is not M4. No production or existing baseline change is authorized.

## Question and oracle

Can the existing descriptor serve repeated autonomous CS-framed four-bit
responses at P=8 internal clocks with minimum public MISO/OE setup of one
clock? The peer independently drives CS/SCK/MOSI and samples the public
24-bit action's MISO bit and OE bit. Debug state diagnoses failures only.
Commands 0/1 select least-significant-bit-first 0x6/0x9. The command rising
edge is CS+4 clocks+SCK phase; response samples follow at command+8,+16,+24,+32.
Normal CS release is CS+38 clocks+release phase. Exact coincident raw events
are driven before the internal rising edge; +/-1 ps witnesses expose this
digital convention, not analog/metastability qualification.

Strict framing requires OE=0 whenever raw CS is high, including after release,
and no emission from an aborted transaction. Autonomous repetition requires
a second selected command after normal release without another START/reset.
Any demonstrated violation rejects this strict contract. Also report, without
promoting it to autonomous success, a weaker bounded contract with per-frame
host START and measured synchronization/turnaround allowance. Do not gate OE
with CS in the testbench. Do not call idle state a successful rearm.

## Baselines and information

The existing test/m3_eventless.v IS M3's edge-reactive baseline, with independent
model/m3_baseline.py. Candidate and edge-reactive are aliases; no distinct
advantage over that baseline is possible. Relative-WAIT uses unchanged
test/m3_countdown.v and the same pre-edge synchronized input. Give WAIT the
best known future schedule: first_delay=ceil(first raw falling edge)-START,
clamped to one if that edge is already past, and spacing=8. This favors WAIT
and explicitly charges it advance schedule knowledge; no extra cancellation
or rearm behavior is added. Neither descriptor contains a timestamp/FIFO.

## Bounded experiment

Sweep delta=CS_assert-START at -8,-6,-4,-2,-1,-0.5,0,+0.5,+1,+2,+4,+6,+8
clocks, both commands, and SCK phases 0, 1 ps, half-clock, clock-1 ps.
Refine first-capture transitions by clock/half-clock and +/-1 ps. Use normal
and varied release phases. Repeated no-reset trains use alternating and same
commands, a long idle, START only once, and per-frame START. Sweep a small
CS-high gap and rearm-START timing grid around the measured capture boundary.
Track every sample/setup, output/OE transition, raw edge, sync stages,
decision, completion/idle/armed state and cross-transaction command attribution.

Directed attacks: early/late/short/missing CS; release before first output,
between bits and +/-1 ps around output; missing/extra SCK; unsupported command
encoding; descriptor busy/not rearmed; immediate next frame; reset during
response/before next frame. A one-bit command admits both 0 and 1; unsupported
encoding means an extra command clock, not an invented opcode. Missing edges
may hold output indefinitely; expose this lack of timeout. There is no timer
or FIFO in either tested descriptor, so wrap and FIFO-full are inapplicable.
Stop at decisive framing/rearm evidence; no huge regression or new architecture.

## Outcome classes and disposition

1. EVENTLESS_SPI_UTILITY_ESTABLISHED: strict framed repetition works and a
   concrete external benefit versus fair ordinary baselines is measured.
2. EVENTLESS_SPI_FUNCTIONAL_BUT_NO_UTILITY_ADVANTAGE: a useful framed contract
   works, but ordinary baselines provide equivalent functionality.
3. EVENTLESS_SPI_FRAMING_INSUFFICIENT: raw-CS/OE or autonomous rearm prevents
   the requested contract, even if coordinated individual responses work.
4. EVENTLESS_SPI_GATE_INCONCLUSIVE: a real technical blocker prevents valid
   comparison; an unfavorable result is not a blocker.

Classes 2/3 end architectural work and lead only to archival documentation.
Class 1 permits a successor proposal, not implementation. Synthesis may map
unchanged test descriptors with equally accounted synchronizers using the
already pinned CMOS5L library; no P&R/STA/physical campaign or area optimization.
Keep source/configuration hashes and curated machine-independent evidence.
