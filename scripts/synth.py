"""Reproducible standalone mapped-area checkpoint; not a LibreLane/STA result.

Set CHRONOS_LIBERTY or PDK_ROOT to the official pinned CMOS5L PDK.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PDK_REV = "2bbec755dc67ca3db0261c3d6163e15735d66710"


def main():
    supplied = os.environ.get("CHRONOS_LIBERTY")
    if supplied:
        library = Path(supplied).resolve()
    elif os.environ.get("PDK_ROOT"):
        library = Path(os.environ["PDK_ROOT"]) / "ihp-sg13cmos5l/libs.ref/sg13cmos5l_stdcell/lib/sg13cmos5l_stdcell_typ_1p20V_25C.lib"
    else:
        raise SystemExit("Set PDK_ROOT or CHRONOS_LIBERTY; see docs/development_setup.md")
    if not library.is_file():
        raise SystemExit(f"CMOS5L Liberty not found: {library}")
    build = ROOT / "build" / "synth"
    build.mkdir(parents=True, exist_ok=True)
    # Copy the library into the run directory to avoid shell/tool path-with-space issues.
    (build / "cells.lib").write_bytes(library.read_bytes())
    for source in (ROOT / "src").glob("*.v"):
        (build / source.name).write_bytes(source.read_bytes())
    script = "\n".join([
        "read_verilog project.v chronos_engine.v chronos_loader.v",
        "synth -top tt_um_chronos -flatten -noabc",
        "dfflibmap -liberty cells.lib",
        "abc -liberty cells.lib",
        "clean", "read_liberty -lib cells.lib", "check -assert", "stat -liberty cells.lib",
        "write_verilog -noattr mapped.v",
        "tee -o stat.json stat -json -liberty cells.lib",
    ])
    (build / "synth.ys").write_text(script + "\n")
    version = subprocess.check_output([os.environ.get("YOSYS", "yosys"), "-V"], text=True).strip()
    subprocess.run([os.environ.get("YOSYS", "yosys"), "-l", "synth.log", "-s", "synth.ys"],
                   check=True, cwd=build, stdout=subprocess.DEVNULL)
    stats = json.loads((build / "stat.json").read_text())
    design = stats["design"]
    source_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT / "src").glob("*.v"))}
    summary = {"scope": "standalone Yosys mapped-area checkpoint, no physical timing",
               "yosys": version, "pdk_revision_expected": PDK_REV,
               "liberty_sha256": hashlib.sha256(library.read_bytes()).hexdigest(),
               "cells": design["num_cells"], "cell_area_um2": design["area"],
               "source_sha256": source_hashes}
    (build / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
