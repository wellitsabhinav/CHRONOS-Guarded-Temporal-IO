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
* [Loom](https://github.com/thomasgilbert481/tt_um_loom): four barrel threads with per-thread deadlines and deadline-latched pin writes that land on a requested clock independently of the thread's instruction slot. This is close competition prior art for M0. Its current README claims an 8×4 implementation; that project's allocation does not change CHRONOS's 6×4 constraint from the official rules. Its verification and physical results have not been independently reproduced here.
* [sjrai007/gp_pae architecture](https://github.com/sjrai007/gp_pae/blob/main/ARCHITECTURE.md): independent programmable sequencer lanes and Hardcaml parameter exploration. Treat design descriptions separately from verified implementation results.
* [2AMLogic/sg13cmos5l-protocol-emulator](https://github.com/2AMLogic/sg13cmos5l-protocol-emulator): public specification-stage timing-oriented programmable processor direction.
* [smprather/serial-protocol-emulator](https://github.com/smprather/janestreet-blog-serial-protocol-emulator): programmable control, tick engine and pin matrix, alongside fixed SERDES/codec helpers. A broader comparison target for the eventual CPU, not evidence of M0 novelty.

M0 is a straightforward member of an established family. The search does
not support claims that CHRONOS is the first timestamped GPIO engine,
deterministic I/O engine, deadline ISA, or CPU-independent waveform queue.
No conclusion about the absence of guarded-future designs follows from a
limited public repository search.
