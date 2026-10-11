"""Run installed official CMOS5L Tiny Tapeout tools; fail clearly if absent."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if not shutil.which("docker"):
    raise SystemExit("Docker is required for local hardening. The retained gds.yaml also runs the official flow in GitHub Actions.")
if os.environ.get("PDK") != "ihp-sg13cmos5l":
    raise SystemExit("Set PDK=ihp-sg13cmos5l and PDK_ROOT; see docs/development_setup.md")
tool = ROOT / "tt" / "tt_tool.py"
if not tool.is_file():
    raise SystemExit("Clone tt-support-tools branch ihp-sg13cmos5l into tt first")
subprocess.run([sys.executable, str(tool), "--ihp", "--create-user-config"], check=True, cwd=ROOT)
subprocess.run([sys.executable, str(tool), "--ihp", "--harden"], check=True, cwd=ROOT)
