# ADR 0001: temporal events before CPU

Status: accepted, 2026-10-11.

Control-flow timing can obscure whether a GPIO scheduler works. Establish
an independently runnable reference model and cycle-level event engine
first. A separate synchronous loader supplies general events. Defer the
CPU and protocols until timing, reset and faults are qualified. This makes
M0 independently falsifiable, but M0 alone is not a competition submission.
