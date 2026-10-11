# M0 synchronous host/test loader

Temporary adapter; not the eventual CPU or external asynchronous interface.
All input pins must be synchronous to `clk`, with setup/hold satisfied.
One command can be sampled on every rising edge while selected (`ena=1`).

| Pins | Meaning |
| --- | --- |
| ui[3:0] | Nibble payload, least significant nibble first |
| ui[6:4] | Command |
| ui[7] | Readback mode (combinational mux of uo; avoid during waveform capture) |
| uio[7:0] | General GPIO input path; unused by M0 command interface |
| uo[7:0] | Scheduled GPIO or readback byte |
| uio_out/oe | Always engine GPIO (masked to zero when deselected) |

| Command | Operation |
| --- | --- |
| 0 | Idle; payload irrelevant |
| 1 | Shift nibble into 56-bit staging word: `{nibble, stage[55:4]}` |
| 2 | COMMIT existing staged event, one-shot; no implicit retry |
| 3 | Clear staging word and nibble count only |
| 4 | Capture a coherent engine snapshot into loader readback register |
| 5 | Shift snapshot right by eight; ignored payload |
| 6, 7 | Reserved no-op |

Exactly 14 SHIFT operations after staging clear/reset/previous COMMIT are
required. Additional SHIFTs saturate the count and retain the most recent
14 nibbles. COMMIT consumes the staging count even on rejection. An
incomplete COMMIT sets loader `format_fault` and makes no engine request.
A complete COMMIT drives core valid at the **same edge**; its timestamp
must be greater than that edge's engine time. Full COMMIT sets overflow,
does not insert, and is not retried. Producer software can poll ready via
snapshot, but capacity may change before COMMIT; inspect the resulting
accepted/rejected/overflow status. Reset clears loader and engine together.

Staging layout, transmitted low nibble first:
`timestamp[31:0]`, `uo[7:0]`, `uio_out[7:0]`, `uio_oe[7:0]`.

CAPTURE reads **pre-edge** state, avoiding incoherent timer bytes:

| Snapshot byte | Contents |
| --- | --- |
| 0 | faults[2:0], format_fault[3], epoch_closed[4], ready[5], accepted[6], executed[7] |
| 1 | occupancy[3:0], rejected[4], remaining bits zero |
| 2..5 | 32-bit time, little endian |
| 6 | engine uo |
| 7 | engine uio_out |
| 8 | engine uio_oe |

In readback mode uo continuously shows the low snapshot byte. CAPTURE does
not pause time or alter the queue. A subsequent command 5 selects the next
byte. Top-level functional tests use real pins and this public readback;
gate tests use the same interface without hierarchical RTL observations.
The adapter cannot sustain one enqueue per clock; core tests establish
maximum dispatch/refill rate independently of loader bandwidth.
