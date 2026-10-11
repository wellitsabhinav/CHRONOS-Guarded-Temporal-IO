# M0 temporal semantics

Normative specification, 2026-10-11. Default parameters: `TIME_W=32`,
`DEPTH=8`, `GPIO_W=24`. Legal depths are positive integers, including one
and non-powers of two. All comparisons are unsigned.

## Clock and epoch

`rst_n` is a **synchronous active-low reset**. Hold it low across at least
one rising edge; deassert with clock setup/hold satisfied. The first active
edge after reset has pre-edge time zero. A cycle labelled T is the edge
whose **pre-edge** timer is T. The post-edge timer normally reads T+1.
Do not label the first active edge cycle one in tests or software.

At each active rising edge, using the pre-edge state:

1. Inspect the existing FIFO head. If its timestamp equals time, atomically
   copy its entire state to GPIO and retire it. If earlier, retire it without
   changing GPIO and set DEADLINE_MISS. At most one entry retires per edge.
2. Consume a producer request if valid and ready. Validate it against the
   **pre-edge** time and last accepted timestamp, then append an immutable
   event if legal. A newly appended event cannot dispatch on this edge.
3. Advance the timer modulo 2^TIME_W.

Reset overrides all three operations, empties the queue, clears sticky
faults, last-accepted history, pulse outputs and epoch status, and sets all
24 GPIO bits to zero (in particular all bidirectional enables are zero).
FIFO data bits are not reset: occupancy determines validity, so stale or
unknown memory cannot dispatch. There are no power-up initializers in production RTL.

## Admission and ordering

`event_ready` means request capacity, not semantic validity. `valid && ready`
consumes a request. `accepted` pulses only for a legal inserted event;
`rejected` pulses for a consumed invalid request. Neither is combinational.
The producer keeps valid and payload stable while waiting for ready.

A legal event satisfies `timestamp > time` and, after any event has been
accepted in this reset epoch, `timestamp > last_accepted_timestamp`.
History remains valid even when the queue empties. Equal times are illegal.
Admission failure does not change the queue or ordering history. If a full
queue retires its head at this edge, ready is high and simultaneous refill
is allowed. There is no empty-FIFO bypass. Earliest legal admission at time
zero is timestamp one, which executes on the next active edge.

An event contains a timestamp and one atomic GPIO state. At default width,
`state[7:0]=uo`, `[15:8]=uio_out`, `[23:16]=uio_oe`, for 56 bits total.
One edge can change data and direction together. Dispatch runs regardless
of producer stalls, invalid requests, or unrelated loader operations.

## Faults and recovery

Sticky until reset; admission conditions can set multiple bits together:

| Bit | Name | Condition and action |
| --- | --- | --- |
| 0 | QUEUE_OVERFLOW | Explicit producer `event_drop` while valid and not ready: a request was abandoned. No insertion. Holding a valid request through backpressure is legal and does not fault. |
| 1 | TIME_ORDER_FAULT | A consumed request is <= the last accepted timestamp; reject it. |
| 2 | DEADLINE_MISS | A consumed request is <= now, or arrives after epoch exhaustion; reject it. Also retire any late head without applying its state. |

`event_drop` is an explicit misuse notification, not a second enqueue path.
The host adapter asserts it on a one-shot COMMIT with no capacity. Faults
are diagnostic: **accepted legal events continue on schedule**. Reset is
the sole recovery/flush operation. A compliant producer cannot create a
late head; tests exercise defensive retirement through deliberate
simulation-only state corruption, distinctly from ordinary stimuli.

## Timer rollover

M0 timestamps belong to one reset epoch, with no scheduling across rollover.
At time `2^TIME_W-1`, the last scheduled event may execute; the timer wraps
to zero and `epoch_closed` becomes sticky. Existing queue state is flushed;
unexpected remaining entries set DEADLINE_MISS. Afterwards time continues
modulo its width but all requests are consumed/rejected with DEADLINE_MISS
and no events execute until reset. GPIO holds its last state. This prevents
an old numerical timestamp from aliasing a future epoch. At 50 MHz a
32-bit epoch lasts about 85.9 seconds. Small-width tests exercise the entire
boundary. Multi-epoch scheduling is a later architectural decision.

## Pin wrapper

See [host interface](host_interface.md). Normal output mode preserves all
24 engine state bits. Readback mode explicitly multiplexes dedicated
outputs, so readback transitions are not scheduled GPIO transitions.
`ena=0` disables command processing and masks pad outputs to zero, including
all output enables; the engine time and dispatch continue. Upon selection,
the current engine state becomes visible. The exact-timing claim assumes
selection, normal output mode, continuous clock, and no reset. These are
operating preconditions, not hidden retiming mechanisms.
