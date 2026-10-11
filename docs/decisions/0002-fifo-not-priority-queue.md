# ADR 0002: ordered FIFO

Status: accepted, 2026-10-11.

Producers must schedule in increasing order. A circular FIFO needs only a
head comparison and a last-accepted admission comparison, avoiding sorting
and queue-wide arbitration. This limits arbitrary insertion and same-time
alternatives. M1 must investigate compact bundles before relaxing ordering.
Default storage is eight 56-bit flop entries; SRAM is premature at 448 bits.
