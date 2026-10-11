# CHRONOS — Guarded Temporal I/O Processor

CHRONOS is a programmable temporal I/O architecture intended to decouple
protocol-edge timing from variable software and control-flow latency.
Accepted future GPIO events retain their scheduled clock edges while the
producer continues working, stalls, or stops.

**Current status: `CHRONOS_M0_PHYSICAL_VERIFIED`**
Official GDS, final STA/DRC/LVS, precheck and all four routed gate suites
pass at qualified head `7166d8b`. Final artifact metrics and production
source equality were inspected. PR closure requires mandatory CI at the
intended merge head, including any subsequent documentation commit.

M0 contains a runnable independent model, a 32-bit timer, an ordered
eight-entry event FIFO, a timestamp dispatcher, atomic 24-bit GPIO state,
sticky faults, and a synchronous programmable loader. **M0 does not
implement guarded speculation, a CPU, or protocol firmware yet.**

## Central idea

```text
normal programmable I/O             CHRONOS

control flow                        control flow
    |                                   |
instruction executes                future event accepted
    |                                   |
pin changes                         producer continues independently
                                        |
                                    dispatcher reaches timestamp
                                        |
                                    pin changes on schedule
```

The intended later research direction is bounded guarded future I/O:

```text
                    unresolved predicate P0
                          /       \
                 waveform A     waveform B
                     |              |
                     +-- prepared --+
                            |
                       P0 resolves
                            |
                    one future survives
                            |
                 original timestamp preserved
```

This is a working hypothesis, not an established novelty claim. Timestamped
GPIO, deterministic I/O, buffered timed output, deadlines, CPU-independent
output compare and first-class time all have prior art. XMOS timed buffered
ports are directly relevant to M0. Read the [research positioning](docs/research/architecture_positioning.md)
and [primary-source survey](docs/research/prior_art.md).

## Competition and architecture

The [Jane Street protocol-emulator competition](https://blog.janestreet.com/protocol-emulator-asic-competition/)
targets open-source programmable ASICs on IHP 130 nm CMOS5L through Tiny
Tapeout. Current allocation is **6×4**, deadline **January 18, 2027**.
CHRONOS starts from the official `cmos5l` template and retains its Apache-2.0
license and prescribed GDS/precheck workflows. M0 alone does not satisfy
the eventual UART/SPI/I²C demonstration requirement.

```text
host loader -> valid/ready -> ordered temporal FIFO -> dispatcher -> GPIO
                                                     ^
                                                32-bit time
```

One 56-bit event contains a timestamp and all `uo`, `uio_out`, `uio_oe`
bits. The dispatcher inspects only the FIFO head. Producers submit strictly
increasing future times; no sorting, heap or queue-wide priority search is
needed. An accepted event is immutable. Faults reject bad requests without
moving already accepted events. Reset clears queue/time/faults and disables
all bidirectional outputs. Timer wrap closes the reset epoch; scheduling
resumes after reset. See [exact cycle semantics](docs/temporal_semantics.md),
[architecture](docs/architecture.md) and [host pin protocol](docs/host_interface.md).

## Run and verify

With Python 3.11+, Icarus/vvp, Verilator and Yosys installed:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r test/requirements.txt
python -m model.cli examples/m0/basic.json
make test
make formal
```

The model prints:

```text
cycle 20: uo=0x55 uio_out=0x00 uio_oe=0x00
cycle 30: uo=0xaa uio_out=0x01 uio_oe=0x01
cycle 50: uo=0x0f uio_out=0x02 uio_oe=0x03
cycle 51: uo=0xf0 uio_out=0x04 uio_oe=0x07
```

Individual targets: `make model-test`, `make rtl-test`, `make diff-test`,
`make lint`, `make synth`, `make formal`, `make harden`. Cell mapping needs
CHRONOS_LIBERTY/PDK_ROOT; hardening needs the official CMOS5L tools, PDK
and Docker. See [portable setup](docs/development_setup.md), including
Windows commands and environment overrides. No machine paths are embedded
in the build scripts.

## Evidence and verification philosophy

The Python deque model and circular FIFO RTL independently implement the
written specification. Tests compare every architectural cycle, not only
final waveforms. Directed tests attack reset, queue boundaries, pointer
wrap, overflow, past/equal deadlines, producer stalls, dense schedules,
long gaps and reduced-width timer wrap. Black-box tests program real top
pins; the same integration tests can run on gates. A bounded SAT proof adds
all-input checks at reduced parameters; it is not an unbounded/full-width
proof. See [verification plan](docs/verification_plan.md) and [results](docs/results/m0_verification.md).

| Check | Current evidence |
| --- | --- |
| Python model | 35 tests pass, including 4096 exhaustive short request streams |
| Core RTL | 24 cocotb cases pass across four width/depth configurations |
| Core differential | 48,000 randomized cycles, seeds 192–195, four width/depth configurations |
| Top pins | Four black-box suites pass |
| Lint/structure | Verilator and Yosys pass |
| Formal | 24-edge bounded SAT pass, TIME_W=4/DEPTH=3/GPIO_W=3 |

## Physical checkpoint

Target: **50 MHz**, **6×4**. Standalone cell mapping is not timing closure.

| Item | Current evidence |
| --- | --- |
| Mapped standard cells | 2,542 (standalone Yosys) |
| Mapped cell area | 58,282.1568 µm² |
| Routed cell utilization | 9.303% excluding filler |
| Worst setup / hold slack | +7.1318 ns / +0.1069 ns across supplied corners |
| Hardening/DRC/precheck/LVS | PASS at qualified head 7166d8b, official run 38153731952 |
| Gate-level integration | Four unchanged pad suites PASS in the official flow |
| FPGA or fabricated silicon | Not tested |

Exact provenance, measurement scope and flow outcome are in
[m0_physical.md](docs/results/m0_physical.md). No raw PDK, toolchain, run
database or waveform is committed.

## Roadmap and limitations

M0 temporal decoupling → M1 guarded futures → M2 programmable control core
→ M3 firmware UART/SPI/I²C → M4 physical qualification.
The next architectural objective is **`CHRONOS_M1_GUARDED_FUTURES`**;
same-timestamp alternatives and predicate commit margins require design
review first. See [roadmap](docs/roadmap.md) and [decision records](docs/decisions/).

Current limits: synchronous host only, 15 clocks per loaded event, FIFO
ordered insertion, one dispatch per clock, no cross-rollover scheduling,
and exact-timing measurement requires continuous selection/clock, normal
output mode and no reset. Readback and deselection intentionally multiplex
or mask pads. There is no CPU, guard/predicate machinery, UART/SPI/I²C,
input capture, analog bus qualification or silicon evidence yet.

## License and development

[Apache-2.0](LICENSE); template attribution is retained in [NOTICE](NOTICE).
This bootstrap, research, implementation and verification were AI-assisted
using Codex. Tests and source-linked evidence support the stated scope;
external engineering review and later hardware validation remain necessary.
