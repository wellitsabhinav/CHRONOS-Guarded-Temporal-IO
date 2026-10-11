"""Bounded M3 peer experiment; no synthesis or physical flow."""
import hashlib
import json
from pathlib import Path
import subprocess
from run_sim import ROOT, run


def main():
    run('m3_eventless','test_m3_baseline',extra_sources=['test/m3_eventless.v'])
    run('m3_peer_tb','test_m3_peer',extra_sources=['test/m3_peer_tb.v','test/m3_eventless.v'])
    result=json.loads((ROOT/'build/m3_peer_tb/m3_peer_timing.json').read_text())
    result['provenance']=dict(frozen_ancestor='4632d7dec8c533090eff4a70dae565d1cba8b260',
        source_sha256={str(p.relative_to(ROOT)).replace('\\','/'):
            hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'src').glob('*.v'))},
        tool_versions=dict(iverilog=subprocess.run(['iverilog','-V'],capture_output=True,text=True).stdout.splitlines()[0]),
        command='python scripts/m3_experiment.py',physical_campaign=False)
    (ROOT/'docs/results/m3_peer_timing.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result['aggregate'],indent=2))


if __name__=='__main__':
    main()
