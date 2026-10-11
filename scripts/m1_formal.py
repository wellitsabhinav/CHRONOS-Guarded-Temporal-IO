"""Small all-input bounded M1 safety proof; no full-width/unbounded claim."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
build=ROOT / "build/m1-formal"
build.mkdir(parents=True,exist_ok=True)
sources=[ROOT / "src/chronos_guarded_engine.v", ROOT / "formal/guarded_top.v"]
for p in sources:
    (build / p.name).write_bytes(p.read_bytes())
(build / "prove.ys").write_text("\n".join([
    "read_verilog -formal chronos_guarded_engine.v guarded_top.v",
    "prep -top guarded_formal_top -flatten", "memory_map", "opt", "dffunmap",
    "setundef -undriven -anyseq", "check -assert",
    "sat -seq 20 -prove-asserts -set-assumes -verify",
])+"\n")
subprocess.run([os.environ.get("YOSYS","yosys"),"-l","formal.log","-s","prove.ys"],
               check=True,cwd=build,stdout=subprocess.DEVNULL)
summary=dict(status="PASS", method="bounded Yosys SAT",edges=20,
             time_w=4,depth=3,gpio_w=2,pred_w=1,gen_w=2,
             scope="wrong-path, mutual exclusion, exact time, miss/no-retiming, generations, reset, FIFO bounds/order/immutability",
             source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
(build / "summary.json").write_text(json.dumps(summary,indent=2)+"\n")
print(json.dumps(summary))
