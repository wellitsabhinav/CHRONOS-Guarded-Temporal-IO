# Prior art survey

Accessed 2026-10-11. This is an engineering survey, not a patent clearance
or exhaustive novelty assessment. Sources are primary vendor publications,
original research, and public authors' repositories.

| System | Established capability relevant to CHRONOS |
| --- | --- |
| [RP2040 PIO, datasheet chapter 3](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf) | Programmable state machines with delay/side-set, FIFOs and pin operations; independent peripheral execution and cycle-controlled waveforms. |
| [TI PRU](https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/10_00_07_04/exports/docs/common/PRU-ICSS/Overview.html) | Programmable real-time processors integrated with I/O/events and local memories; timing-sensitive protocols can be software workloads. |
| [NXP FlexIO](https://www.nxp.com/docs/en/application-note/AN13358.pdf) | Configurable shifters/timers/pins emulate protocols; efficient peripheral emulation already exists. |
| [XMOS AN03002](https://www.xmos.com/documentation/XM-015260-AN/pdf/AN03002_v1.0.0.pdf) | Timed output buffers values until port time equals a requested timestamp, allowing intervening processor work. This is direct prior art for M0 decoupling. |
| [PRET project and papers](https://ptolemy.berkeley.edu/projects/chess/pret/) | Repeatable processor timing, deadline instructions and precision-timed I/O; first-class time is established. |
| [PTIDES original report](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2008/EECS-2008-72.html) | Timestamped events tied to physical/model time, safe processing and independent computation scheduling. Distributed semantics differ from this local FIFO. |
| [ST AN4776](https://www.st.com.cn/resource/en/application_note/an4776-how-to-use-generalpurpose-timer-peripheral-on-stm32-mcus-stmicroelectronics.pdf) | Output compare/PWM/timer-triggered waveform production independent of immediate CPU execution. |

## Public competition work searched now

Searches included Jane Street protocol emulator, deadlines, timestamps,
multithreading and event scheduling. This snapshot is non-exhaustive and
repository claims below have not been independently reproduced.

* [Tempo](https://github.com/satyaammu93/jane-street-asic-2026/tree/main/protocol_emulator): two programmable engines, pin/timestamp capture, bounded waits and firmware protocols. Its published reports claim CMOS5L qualification. Timing capture and event coordination overlap the broader design space.
* [Abagel-coder/protocol-emulator](https://github.com/Abagel-coder/protocol-emulator): time-triggered programmable core with WAIT/DELAY/deadline direction; a different implementation of temporal protocol execution is already public.
* [Loom](https://github.com/thomasgilbert481/tt_um_loom): four barrel threads with per-thread deadlines and deadline-latched pin writes independent of the thread's instruction slot. This is close competition prior art for M0. Its current README reports 6×4; the earlier 8×4 observation is superseded. Its verification and physical claims have not been independently reproduced here.
* [sjrai007/gp_pae architecture](https://github.com/sjrai007/gp_pae/blob/main/ARCHITECTURE.md): independent programmable sequencer lanes and Hardcaml parameter exploration. Treat design descriptions separately from verified implementation results.
* [2AMLogic/sg13cmos5l-protocol-emulator](https://github.com/2AMLogic/sg13cmos5l-protocol-emulator): public specification-stage timing-oriented programmable processor direction.
* [smprather/serial-protocol-emulator](https://github.com/smprather/janestreet-blog-serial-protocol-emulator): programmable control, tick engine and pin matrix, alongside fixed SERDES/codec helpers. A broader comparison target for the eventual CPU, not evidence of M0 novelty.

M0 is a straightforward member of an established family. The search does
not support claims that CHRONOS is the first timestamped GPIO engine,
deterministic I/O engine, deadline ISA, or CPU-independent waveform queue.
No conclusion about the absence of guarded-future designs follows from a
limited public repository search.

## Focused M1 mechanism check (2026-10-11)

Question: does one pre-materialized alternative bundle, resolved later through
a registered generation token, with exact timestamp selection and fail-closed
miss retirement, offer useful competition differentiation?

**ESTABLISHED FACT from the cited source:** XMOS AN03002 sections 2/3 buffers
output and starts timed output on a selected port clock. RP2040 chapter 3
provides JMP PIN, WAIT, delayed instructions and side-set. PRU is programmable
real-time I/O, and FlexIO AN13358 demonstrates configurable protocol emulation.
PRET/PTIDES and STM32 output compare already establish explicit timing and
timestamp-oriented execution. None of those broad capabilities is claimed
as CHRONOS novelty.

The closest examined competition source is
[Loom semantics section 6.10](https://github.com/thomasgilbert481/tt_um_loom/blob/main/docs/SEMANTICS.md):
one staged `(pin,value)` fires at the thread deadline; replacement staging
and an already-late deadline may apply a write at a later instruction commit.
The inspected contract does not describe CHRONOS's atomic two-alternative,
generation-matched bundle or unresolved-miss retirement. That is a narrow
source comparison, not proof that Loom cannot implement similar behavior.
RP2040's JMP PIN followed by output is already a small conditional reaction;
do not equate our chosen three-stage baseline with its optimum implementation.

**INFERENCE / WORKING HYPOTHESIS:** CHRONOS offers a compact programming
contract for preparing complete data+OE alternatives before a decision, with
one resolver write sufficient one accepted clock before a fixed deadline.
This removes subsequent software action construction/issue from that deadline
path. A specialized mux or comparable guarded peripheral could match it.
The distinction lies in the programmable contract and safety policy, not a
new law of timing, general speculation or uniqueness of conditional GPIO.

**UNPROVEN CLAIM:** first implementation, patentability, globally novel
mechanism, optimal area, or measured superiority to any named architecture.
The limited search supports retaining M1 for M2 integration, not marketing
those claims. Reassess if programmable integration consumes disproportionate
area or if actual UART/SPI/I2C control paths gain no useful slack.

## M2 utility result (2026-10-11)

The implemented programmable fused ordinary sampler matches guard margin,
four-bit SPI-like response success and drained restart throughput. The earlier
M1 conceptual branch/enqueue baseline does not establish a retained practical
advantage. M2 therefore defaults to ordinary operation and records NO-GO for
guards. This falsifies the measured utility hypothesis for the tested workload;
it does not establish that every conceivable guarded workload lacks value or
that any named prior architecture is equivalent. See the
[M2 A–N report](../results/m2_initial_evaluation.md).
