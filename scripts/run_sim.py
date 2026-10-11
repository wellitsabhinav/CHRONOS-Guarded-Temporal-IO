"""Portable cocotb/Icarus runner; no make or shell path quoting required."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def run(top, module, parameters=None, extra_sources=()):
    from cocotb_tools import config
    from find_libpython import find_libpython
    build = ROOT / "build" / top
    if parameters:
        build = build / "-".join(f"{key}{value}" for key, value in parameters.items())
    build.mkdir(parents=True, exist_ok=True)
    command = [os.environ.get("IVERILOG", "iverilog")]
    if os.environ.get("IVERILOG_BASE"):
        command += ["-B", os.environ["IVERILOG_BASE"]]
    command += ["-g2005", "-Wall", "-s", top, "-o", str(build / "sim.vvp")]
    for key, value in (parameters or {}).items():
        command += [f"-P{top}.{key}={value}"]
    command += [str(path) for path in sorted((ROOT / "src").glob("*.v"))]
    command += [str(ROOT / path) for path in extra_sources]
    if top in ("tb", "engine_tb"):
        command += [str(ROOT / "test" / f"{'tb' if top == 'tb' else 'engine_tb'}.v")]
    subprocess.run(command, check=True, cwd=ROOT)
    env = os.environ.copy()
    env.update(PYTHONPATH=os.pathsep.join([str(ROOT), str(ROOT / "test"), env.get("PYTHONPATH", "")]),
               COCOTB_TEST_MODULES=module, COCOTB_TOPLEVEL=top,
               PYGPI_PYTHON_BIN=sys.executable, LIBPYTHON_LOC=find_libpython(),
               COCOTB_RESULTS_FILE=str(build / "results.xml"))
    env.update({f"CHRONOS_{key}": str(value) for key, value in (parameters or {}).items()})
    plugin = str(config.lib_name_path("vpi", "icarus"))
    subprocess.run([os.environ.get("VVP", "vvp"), "-M", str(Path(plugin).parent),
                    "-m", Path(plugin).name, str(build / "sim.vvp")],
                   check=True, cwd=build, env=env)
    report = ET.parse(build / "results.xml")
    cases = report.findall(".//testcase")
    if not cases or report.findall(".//failure") or report.findall(".//error"):
        raise SystemExit("cocotb tests failed; inspect build results.xml")
    if module.startswith(("test_m2", "test_programmable")):
        (build / f"{module}_results.xml").write_bytes((build / "results.xml").read_bytes())
    print(f"PASS: {top} {parameters or {}} ({len(cases)} cocotb tests)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", choices=["core", "top", "all", "guarded"], default="all", nargs="?")
    args = parser.parse_args()
    if args.suite in ("core", "all"):
        for width, depth in [(32, 8), (8, 1), (8, 3), (4, 8)]:
            run("engine_tb", "test_engine", {"TIME_W": width, "DEPTH": depth})
    if args.suite in ("top", "all"):
        run("tb", "test")
    if args.suite == "guarded":
        for depth in [1, 3]:
            run("chronos_guarded_engine", "test_guarded", {"TIME_W": 8, "DEPTH": depth,
                                                           "PRED_W": 1, "GEN_W": 2})


if __name__ == "__main__":
    main()
