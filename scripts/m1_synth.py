"""One paired M0/M1 core mapping, same Liberty/tool/default queue parameters."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def main():
    library=Path(os.environ["CHRONOS_LIBERTY"]).resolve()
    yosys=os.environ.get("YOSYS","yosys")
    version=subprocess.check_output([yosys,"-V"],text=True).strip()
    results={}
    for name,top in [("m0","chronos_engine"),("m1","chronos_guarded_engine")]:
        build=ROOT / "build/m1-synth" / name
        build.mkdir(parents=True,exist_ok=True)
        source=ROOT / "src" / (top+".v")
        (build / "core.v").write_bytes(source.read_bytes())
        (build / "cells.lib").write_bytes(library.read_bytes())
        (build / "map.ys").write_text("\n".join([
            "read_verilog core.v",f"synth -top {top} -flatten -noabc",
            "dfflibmap -liberty cells.lib", "abc -liberty cells.lib",
            "clean", "read_liberty -lib cells.lib", "check -assert",
            "tee -o stat.json stat -json -liberty cells.lib"
        ])+"\n")
        subprocess.run([yosys,"-l","synth.log","-s","map.ys"],check=True,cwd=build,stdout=subprocess.DEVNULL)
        design=json.loads((build / "stat.json").read_text())["design"]
        flops=sum(n for cell,n in design["num_cells_by_type"].items() if "dff" in cell or "dfr" in cell or "sdf" in cell)
        results[name]=dict(cells=design["num_cells"],area_um2=design["area"],flops=flops,
                           source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                           cell_types=design["num_cells_by_type"])
    summary=dict(scope="observable standalone cores; excludes pad loader, CTS/routing/STA",
                 yosys=version,liberty_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),
                 time_w=32,depth=8,gpio_w=24,m1_pred_w=2,m1_gen_w=8,results=results,
                 delta={key:results["m1"][key]-results["m0"][key] for key in ["cells","area_um2","flops"]})
    (ROOT / "build/m1-synth/summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary,indent=2))


if __name__=="__main__":
    main()
