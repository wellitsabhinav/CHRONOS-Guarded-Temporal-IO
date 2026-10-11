"""Fail on Verilator diagnostics; check Yosys structural correctness as well."""
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
sources = [str(path.relative_to(ROOT)).replace("\\", "/") for path in sorted((ROOT / "src").glob("*.v"))]
verilator = os.environ.get("VERILATOR") or shutil.which("verilator")
if not verilator:
    raise SystemExit("Verilator is required; install it or set VERILATOR")
# Filename is the inherited Tiny Tapeout project.v; module name is mandated tt_um_*.
subprocess.run([verilator, "--lint-only", "--Wall", "-Wno-DECLFILENAME",
                "--top-module", "tt_um_chronos", *sources], check=True, cwd=ROOT)
subprocess.run([os.environ.get("YOSYS", "yosys"), "-Q", "-T", "-p",
                f"read_verilog {' '.join(sources)}; hierarchy -check -top tt_um_chronos; proc; check -assert"],
               check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
print("PASS: Verilator lint and Yosys structural check")
