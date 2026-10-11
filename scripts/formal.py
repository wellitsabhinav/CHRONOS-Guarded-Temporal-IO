"""Bounded Yosys SAT proof: all input sequences for 24 abstract rising edges.

Reduced parameters cover rollover and non-power-of-two FIFO wrap. This is
bounded evidence, not an unbounded proof or SymbiYosys qualification.
"""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
build = ROOT / "build" / "formal"
build.mkdir(parents=True, exist_ok=True)
for source in [ROOT / "src/chronos_engine.v", ROOT / "formal/top.v"]:
    (build / source.name).write_bytes(source.read_bytes())
script = "\n".join([
    "read_verilog -formal chronos_engine.v top.v",
    "prep -top formal_top -flatten",
    "memory_map", "opt", "dffunmap",
    # Non-power-of-two memory mux padding is unspecified, never a legal address.
    "setundef -undriven -anyseq", "check -assert",
    "sat -seq 24 -prove-asserts -set-assumes -verify",
])
(build / "prove.ys").write_text(script + "\n")
subprocess.run([os.environ.get("YOSYS", "yosys"), "-l", "formal.log", "-s", "prove.ys"],
               check=True, cwd=build, stdout=subprocess.DEVNULL)
summary = {"status": "PASS", "method": "bounded Yosys SAT", "edges": 24,
           "time_w": 4, "depth": 3, "gpio_w": 3,
           "scope": "reset, due-only execution, immutable slots, output-change causes, FIFO retirement and order admission"}
(build / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary))
