# Reproducible development setup

Use Python 3.11+ with Icarus, vvp, Verilator and Yosys on PATH. Linux is
the official physical-flow environment. Functional verification also runs
on Windows with compatible native cocotb/Icarus binaries.

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r test/requirements.txt
make test
make formal
python -m model.cli examples/m0/basic.json
```

On PowerShell activate `.venv/Scripts/Activate.ps1`, then use `make
PYTHON=python test` or the equivalent Python scripts directly. `make test`
runs the core differential suite and top tests once, alongside model tests
and lint. `make diff-test` reruns just the core when needed. Tests inspect
JUnit results and return failure even if a simulator's exit code is zero.

Tool overrides: IVERILOG, VVP, IVERILOG_BASE, VERILATOR, VERILATOR_ROOT and
YOSYS. These are environment settings, never machine paths in source.
Some native Icarus builds mishandle spaces in the helper directory. Copy
their unchanged `lib/ivl` directory into a temporary directory without
spaces and set IVERILOG_BASE to that copy. Some native Verilator builds
similarly need a space-free copy of `share/verilator` as VERILATOR_ROOT,
and their `verilator_bin` executable as VERILATOR. No source/tool patch is
required. A standard Linux install requires neither workaround.

## Standalone cell mapping

Use the official [CMOS5L action's PDK revision](https://github.com/TinyTapeout/tt-gds-action/blob/ihp-cmos5l/install_sg13cmos5l.sh),
currently `2bbec755dc67ca3db0261c3d6163e15735d66710`. Set PDK_ROOT to its
checkout parent, or CHRONOS_LIBERTY to
`ihp-sg13cmos5l/libs.ref/sg13cmos5l_stdcell/lib/sg13cmos5l_stdcell_typ_1p20V_25C.lib`.
Then `make synth`. This uses Yosys synth/dfflibmap/ABC and records cell count,
area, library/source hashes and version in ignored `build/synth/summary.json`.
It is an early area checkpoint, not the official hardening result or STA.

## Official hardening and precheck

Retained `.github/workflows/gds.yaml` runs the prescribed CMOS5L GDS,
precheck and gate tests on pushes. Viewer deployment additionally needs
GitHub Pages configured for Actions; a viewer deployment failure alone
does not prove a GDS failure. Documentation uses the retained docs action.

For local Linux hardening install Docker and LibreLane `3.1.0.dev3`, clone
`TinyTapeout/tt-support-tools` branch `ihp-sg13cmos5l` into ignored `tt`,
and install its requirements. Install the pinned IHP PDK as described in
the competition action. Set PDK_ROOT, `PDK=ihp-sg13cmos5l` and run
`make harden`. Run `tt/tt_tool.py --ihp --print-warnings` and inspect the
reports. The official action provides precheck installation and invocation;
see [action source](https://github.com/TinyTapeout/tt-gds-action/blob/ihp-cmos5l/precheck/action.yml).
Do not replace the competition action with generic sg13g2 instructions.

Do not commit environments, downloaded PDKs/tools, run databases or waves.
Promote only curated summaries with provenance into docs/results. Any flow
repair must be reproduced and isolated from CHRONOS correctness results.
