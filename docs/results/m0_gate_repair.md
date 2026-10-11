# M0 gate simulation integration repair

Failure class: **tool integration / test configuration**, reproduced from
[job 114504657784](https://github.com/wellitsabhinav/CHRONOS-Guarded-Temporal-IO/actions/runs/38148339314/job/114504657784)
at physical head `98dff4f2b9f9350ab1fc403a924c0ff4fc0f884d`.
1238 elaboration errors occur before tests, including unknown `ihp_dff_r`.
The gate Makefile omitted the official PDK's `sg13cmos5l_udp.v`.

The same pinned cell model also connects sequential logic to `delayed_*`
timing-check arguments. Icarus functional simulation does not implement
those timing checks, leaving delayed inputs undriven. The functional view
generator removes specify blocks and substitutes actual input pins for
their delayed counterparts. UDP truth tables and cell logic are unchanged.
This is an explicit zero-delay GLS compatibility adapter, **not SDF timing
validation**. Extracted STA remains mandatory and no RTL/config/action pin
or timing target changes. Both the official gate action's Makefile and a
portable routed-netlist runner use the same adapter.

PDK: IHP-GmbH/IHP-Open-PDK
`2bbec755dc67ca3db0261c3d6163e15735d66710`,
[cell models](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/2bbec755dc67ca3db0261c3d6163e15735d66710/ihp-sg13cmos5l/libs.ref/sg13cmos5l_stdcell/verilog/sg13cmos5l_stdcell.v),
[UDP definitions](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/2bbec755dc67ca3db0261c3d6163e15735d66710/ihp-sg13cmos5l/libs.ref/sg13cmos5l_stdcell/verilog/sg13cmos5l_udp.v).
Do not commit generated libraries or downloaded netlists.

Local reproduction (2026-10-11, Python 3.12.4/cocotb 2.0.1/Icarus 12.0):

```sh
python scripts/run_gates.py /path/to/tt_um_chronos.v /path/to/pdk/verilog
```

**PASS: all four existing black-box top-pin suites** on the actual routed
netlist from artifact 11706624174, including 2657 clocks of randomized host
operations. No test body or assertion was modified or skipped.
CI confirmation and precheck are still required before M0 closure.
The separate viewer failure is Pages configuration (404 on deploy), not a
layout/check failure. The official GDS workflow is retained unchanged.
