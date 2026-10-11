# M0 verification plan

Normative oracle: [temporal semantics](temporal_semantics.md).

* Layer A: independent deque-based model, 35 unit cases including 4096
  exhaustive four-request streams at three-bit time/depth two.
* Layers B/C: cocotb directly clocks the core and compares time, occupancy,
  full GPIO state, sticky faults, epoch status, acceptance/rejection and
  execution every cycle against the model. Test arithmetic is not generated
  from RTL and no shared executable transition implementation exists.
* Layer D: seeds 192..195, 3000 cycles each per configuration: TIME_W/DEPTH
  32/8, 8/1, 8/3, 4/8. Total 48,000 randomized compared cycles, in addition
  to directed suites. Record admission/execution totals so idle-only runs
  cannot masquerade as meaningful comparison.
* Black-box integration: real Tiny Tapeout pins and public snapshot loader,
  including programmable atomic direction/data changes. The same four suites
  are usable on routed gates without hierarchical debug signals.
* Layer E: Yosys bounded SAT, 24 edges with TIME_W=4, DEPTH=3, GPIO_W=3,
  arbitrary producer payload/valid/reset/drop. Initial reset is assumed;
  later resets are unconstrained. Properties cover due-only execution,
  storage retention and admission order, reset-safe outputs and occupancy,
  output-change causes and ordered head retirement. Nonexistent padded
  memory mux addresses are unconstrained; assertions bound actual pointers
  and the symbolic observed slot to valid addresses. This is not an
  unbounded proof or full-width formal result.

Directed tests cover empty, single, full, waiting valid, abandoned request,
simultaneous full pop/refill, repeated pointer wraps, depth one, non-power
of two, adjacent/dense events, long sparse gaps, far future, now/past/order
rejection, reset before/on/after dispatch, full reset, reuse and closed-epoch
wrap. Producer independence replays identical accepted schedules with idle,
continuous unrelated activity and randomized stalls. Curated expected
canonical trace is version controlled; large waves are ignored.

The top loader needs 15 cycles per event, so its canonical integration
schedule is 100,110,150,151. The core tests retain 20,30,50,51 and establish
one event/clock dispatch/refill independently of loader bandwidth.

Defensive late-head behavior is a separate corruption test; such a head
cannot arise from legal accepted M0 requests. Never hide a model/RTL
disagreement by adding delays. Reproduce, identify the violated semantics,
add a failing regression, fix the root cause, then rerun nearby/random tests.
Synthesis and physical timing/layout checks are independent evidence layers.
