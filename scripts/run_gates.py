"""Run existing black-box pad tests on an official routed netlist, no SDF."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from pdk_functional import prepare

ROOT = Path(__file__).resolve().parents[1]


def main():
    from cocotb_tools import config
    from find_libpython import find_libpython
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("netlist", type=Path)
    parser.add_argument("model_dir", type=Path)
    args = parser.parse_args()
    build = ROOT / "build/gates"
    build.mkdir(parents=True, exist_ok=True)
    cells = prepare(args.model_dir / "sg13cmos5l_stdcell.v", build / "functional.v")
    command = [os.environ.get("IVERILOG", "iverilog")]
    if os.environ.get("IVERILOG_BASE"):
        command += ["-B", os.environ["IVERILOG_BASE"]]
    command += ["-g2005", "-DGL_TEST", "-s", "tb", "-o", str(build / "sim.vvp"),
                str(cells), str(args.model_dir.resolve() / "sg13cmos5l_udp.v"),
                str(args.netlist.resolve()), str(ROOT / "test/tb.v")]
    subprocess.run(command, check=True)
    env = os.environ.copy()
    env.update(PYTHONPATH=os.pathsep.join([str(ROOT), str(ROOT / "test")]),
               COCOTB_TEST_MODULES="test", COCOTB_TOPLEVEL="tb",
               PYGPI_PYTHON_BIN=sys.executable, LIBPYTHON_LOC=find_libpython(),
               COCOTB_RESULTS_FILE=str(build / "results.xml"))
    plugin = Path(config.lib_name_path("vpi", "icarus"))
    subprocess.run([os.environ.get("VVP", "vvp"), "-M", str(plugin.parent),
                    "-m", plugin.name, str(build / "sim.vvp")], check=True, cwd=build, env=env)
    report = ET.parse(build / "results.xml")
    cases = report.findall(".//testcase")
    if not cases or report.findall(".//failure") or report.findall(".//error"):
        raise SystemExit("gate tests failed")
    print(f"PASS: {len(cases)} routed-netlist pad suites (zero-delay, no SDF)")


if __name__ == "__main__":
    main()
