# CHRONOS verification

From the repository root, `make test` runs model tests, core differential
tests in four parameter configurations, four black-box top-pin suites,
and lint. `make formal` runs the reduced-parameter bounded SAT proof.
`scripts/run_sim.py` is the portable cocotb/Icarus runner; it validates the
JUnit results as well as the simulator exit code. See
[setup](../docs/development_setup.md) and [results](../docs/results/m0_verification.md).

`test_engine.py` compares architectural state every edge against the
independent Python model. `test.py` drives only the standard top pins and
is reused by the official Tiny Tapeout gate workflow. The loader is
documented in [host_interface.md](../docs/host_interface.md).

The inherited Makefile remains the official action's entry point. Locally:

```sh
cd test
make -B
```

For gate simulation, install the official CMOS5L PDK/tool environment,
copy the hardened `tt_um_chronos` powered netlist to the ignored
`test/gate_level_netlist.v`, and run `make -B GATES=yes`. The official GDS
workflow performs this setup automatically.

Waves are disabled by default. Add `-DWAVES` to compilation when debugging,
then use GTKWave or Surfer on the generated FST/VCD. `tb.gtkw` references
relative paths. Generated waves and netlists are ignored.
