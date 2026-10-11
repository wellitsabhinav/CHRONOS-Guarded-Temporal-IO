# M0 physical checkpoint

Recorded 2026-10-11. Target: **6×4 tiles, 50 MHz (20 ns)**,
`tt_um_chronos`, IHP 130 nm CMOS5L. Production parameters are TIME_W=32,
DEPTH=8, GPIO_W=24, with the programmable host loader included.

Current classification: **CHRONOS_M0_LOGIC_VERIFIED_PHYSICAL_PENDING**.
Functional evidence is [m0_verification.md](m0_verification.md).

## Standalone mapped-area result

**PASS** using `make synth` with the official pinned typical-corner
`sg13cmos5l_stdcell_typ_1p20V_25C.lib` supplied through CHRONOS_LIBERTY.
The script performs synth, dfflibmap, ABC, library loading and structural
checking, and records hashes and tool version. Reproduction is documented
in [development_setup.md](../development_setup.md).

| Measurement | Standalone Yosys result |
| --- | ---: |
| Mapped standard cells | 2,542 |
| Cell area | 58,282.1568 µm² (0.0582822 mm²) |
| Resettable D flip-flops | 690 |
| SRAM macros | 0 |

Yosys: 0.30+48, git `b5b0b7e83`. Full source/Liberty SHA-256 values:
[m0_synthesis.json](m0_synthesis.json). This maps the complete loadable top,
not a hard-coded waveform or an engine optimized away from unused pins.
These numbers exclude physical filler/decap/tap/clock/routing additions
and **do not establish timing closure or routed utilization**.

## Official flow provenance

The unchanged competition workflow is
[gds.yaml](../../.github/workflows/gds.yaml). The measured run is
[38148339314](https://github.com/wellitsabhinav/CHRONOS-Guarded-Temporal-IO/actions/runs/38148339314),
at commit `98dff4f2b9f9350ab1fc403a924c0ff4fc0f884d`. Later documentation,
test and development-container edits leave its production RTL, info.yaml
and physical configuration unchanged; normalized RTL hashes identify the
hardware being measured.

Verified official sources/pins used for the checkpoint:

| Component | Revision/configuration |
| --- | --- |
| Template | TinyTapeout/ttihp-verilog-template `cmos5l`, b86a2a781484bcab7ba522dc5de540086695a430 |
| Competition action | TinyTapeout/tt-gds-action `ihp-cmos5l`, checked at 3412659307918422f3f0727917cf9b499aaca588 |
| LibreLane action pin | 3.1.0.dev3 |
| Support tools | `ihp-sg13cmos5l`, checked at d66cf179e7bc4d296362ab7e2e3b344dc3c4f665 |
| IHP PDK action pin | 2bbec755dc67ca3db0261c3d6163e15735d66710 |
| Physical config | Inherited config.json; CLOCK_PERIOD=20, PL_TARGET_DENSITY_PCT=60 |
| 6×4 outline in support tools | 1289.28 × 710.64 µm; actual flow outline, not nominal competition area |

The 60% placement setting is a requested target, **not measured utilization**.
Branch tags can move; these checked revisions and the actual run identify
the evidence. The general Tiny Tapeout sg13g2 hardening guide is not a
replacement for the competition's CMOS5L action.

## Hardening and signoff status

| Check | Status |
| --- | --- |
| Official GDS build | RUNNING; routed layout export reached |
| Setup WNS / hold WNS | Not yet extracted from final reports |
| Routing DRC | Live router reported 0 remaining violations; final signoff pending |
| Magic DRC / LVS | Pending final reports |
| Tiny Tapeout precheck | Pending GDS completion |
| Gate-level top-pin tests | Pending GDS completion |
| Hardening runtime | Pending job completion |
| FPGA / silicon | Not run |

Local hardening was attempted through `make harden`; the script reports
the exact missing prerequisite, Docker. No native OpenROAD/LibreLane or
usable local Linux/Docker environment was available. GitHub Actions runs
the official flow instead. There are no local physical-tool source patches
or modified action pins. Final reports, not intermediate routing messages,
determine physical PASS.

## Interpretation and next gate

The unoptimized 448-bit flop event store and 32-bit timing/admission logic
have a modest standalone mapped area. That supports continuing physical
measurement; it does not yet answer the 50 MHz routed timing question.
Do not lower the target without diagnosing any final timing failure.
Complete official hardening/STA/DRC/LVS/precheck/gate evidence before
promoting the classification. Preserve raw outputs only as ignored local
files or GitHub artifacts; commit curated metrics with provenance.

The next architectural objective remains
**CHRONOS_M1_GUARDED_FUTURES**, beginning with same-timestamp alternative
semantics and predicate-resolution margin design. M0 contains no guards,
CPU, UART/SPI/I²C firmware or fabricated-silicon evidence.
