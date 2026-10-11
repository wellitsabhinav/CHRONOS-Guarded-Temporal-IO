# CHRONOS architecture

M0 establishes a producer-independent temporal output substrate:

```text
synchronous nibble loader -> valid/ready -> ordered FIFO -> head comparator
                                               ^               |
                                               |               v
                                         32-bit time       24-bit GPIO
```

`chronos_engine` owns time, immutable event storage, ordering history,
admission validation, dispatch, and sticky faults. `chronos_loader` owns
only the staging word and request conversion. `tt_um_chronos` maps the
standard Tiny Tapeout pins and exposes readback without test-only ports.
Core occupancy/time/pulse ports provide limited architectural observability
for a future producer and unit verification.

The FIFO is a circular array with explicit wrap at DEPTH-1. Capacity counts
are updated for simultaneous push/pop, including DEPTH=1. Only the head
timestamp participates in dispatch; only last accepted time participates
in admission ordering. Storage can remain uninitialized because zero
occupancy after reset prevents stale storage from becoming an event.

No CPU, instruction memory, ISA, assembler, protocol block, predicate table,
speculation, DMA, CAM, priority queue, or multithreading exists in M0.
An internal event is general GPIO state, not a preprogrammed waveform.

Logical exactness means the RTL output register changes at the specified
clock edge. Pad delays, clock jitter, timing closure, and silicon behavior
require physical and hardware evidence. See [semantics](temporal_semantics.md)
and [physical evidence](results/m0_physical.md).
