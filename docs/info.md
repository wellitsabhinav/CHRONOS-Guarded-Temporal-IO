# How it works

This page documents the historical qualified M0 pad top. CHRONOS architectural
development ended after negative M2/M3/eventless utility gates. See the
repository's final eventless A–N report; no successor hardware is planned.

CHRONOS M0 accepts future atomic GPIO states into an eight-entry ordered
FIFO. A 32-bit timer dispatches the head at its timestamp independently
of later host activity. Every event updates eight dedicated outputs,
eight bidirectional outputs and eight bidirectional enables together.

M0 was the temporal substrate for the guarded temporal I/O research hypothesis.
It does not yet contain a CPU, guarded futures or UART/SPI/I2C firmware.
Timed buffered I/O has established prior art; no novelty claim is made
for M0. See the repository research notes for primary references.

Timestamp T means the rising clock edge with pre-edge timer T. The timer
resets to zero. A new event must be strictly in the future and later than
every event previously accepted since reset. Equal-time or past events
are rejected. Sticky overflow, order and deadline status is available
through a coherent snapshot. Faults do not retime accepted events.
At timer wrap the scheduling epoch closes until reset.

# How to test

Drive clk continuously at up to the qualified clock rate. The design
target is 50 MHz; consult the physical report before treating that target
as achieved. Hold rst_n low across at least one rising edge, then high.
All host inputs are synchronous to clk. Select the design with ena high.

Set ui[6:4] to command 1 and send the event's 14 nibbles on ui[3:0],
least significant nibble first, one per clock. The 56-bit word is
timestamp[31:0], uo[7:0], uio_out[7:0], uio_oe[7:0] in increasing
bit positions. Command 2 commits the word at that edge. Load sufficiently
ahead of time; a complete word takes 15 edges to send and commit.

Command 0 idles, 3 clears staging, 4 captures status/time/state, and 5
advances the snapshot by one byte. With ui[7]=1, uo shows the current
snapshot byte. Snapshot bytes are status, occupancy/rejection, four time
bytes (little endian), uo, uio_out and uio_oe. Status bits 0..2 are
overflow/order/deadline, bit 3 is malformed-loader status, bit 4 is closed
epoch, bit 5 is ready, bit 6 accepted, bit 7 executed. Capture samples
pre-edge values. Use normal ui[7]=0 while measuring scheduled outputs.

Example: load states for T=100,110,150,151 during the first 60 active
edges, then idle or shift unrelated staging nibbles. The four scheduled
updates must occur at the same edges in every run. Repository tests also
exercise the core canonical timestamps 20,30,50,51.

Reset clears queue, time, faults, staging and all GPIO. Dedicated outputs
become zero and bidirectional enables become zero on the reset edge.
ena low masks all outputs/enables and ignores loader commands, while
internal time/dispatch continue. Re-selection reveals the current state.

# External hardware

A synchronous host/FPGA or test controller. No external oscillator beyond
clk is required. No actual board bring-up or fabricated-silicon behavior
has been verified. Autonomous shared-bus SPI behavior failed the final utility
gate; electrical bus qualification was not performed.
