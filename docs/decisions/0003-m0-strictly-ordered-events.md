# ADR 0003: strict ordering and bounded epoch

Status: accepted, 2026-10-11.

Order history persists until reset, even after drain. Duplicate timestamps
are rejected; one event atomically carries every output bit and direction.
Use unsigned 32-bit times with a closed epoch on wrap. This supports the
whole numeric future range without half-range modular comparisons, at the
cost of reset after about 85.9 seconds at 50 MHz. Faults do not cancel
previously accepted events. Define legal backpressure separately from
explicit request abandonment (`event_drop`) so waiting does not overflow.
