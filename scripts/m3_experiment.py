"""Bounded M3 peer experiment; no synthesis or physical flow."""
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
from run_sim import ROOT, run


def curate(result):
    """Keep every candidate/sample metric in CSV; retain small JSON witnesses."""
    paths=('chronos','eventless','relative_wait')
    flattened=[]
    for case_id,row in enumerate(result['rows']):
        for path in paths:
            metrics=row[path]
            for sample in metrics['samples']:
                flat=dict(case_id=case_id,path=path,**row['point'],peer_edges=row['peer_edges'],
                    success=metrics['success'],sampled_bits_correct=metrics['sampled_bits_correct'])
                for key in ('E','stage1','stage2','S','R','A','E_to_S','S_to_R','R_to_A',
                            'A_to_O','E_to_O','E_to_T','worst_setup','average_setup','issue_stalls',
                            'max_occupancy','final_faults','final_sampler_busy','completion','final_gpio'):
                    flat[key]=metrics[key]
                flat.update(sample)
                flattened.append(flat)
    with (ROOT/'docs/results/m3_peer_samples.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(flattened[0]))
        writer.writeheader();writer.writerows(flattened)
    selected=[]
    for row in result['rows']:
        p=row['point']
        regular=(p['name']=='period_phase' and p['value']==1 and p['period'] in (60000,70000,80000)
                 and p['phase'] in (0,1,5000,9999))
        witness=(p['name'] in ('missing_command','missing_fall','extra_edge','unexpected_cs',
                              'falling_selected_edge','reset_near_response') or
                 p['name']=='setup_requirement' and p['period']==80000 and p['required_setup']==20000 and p['phase']==1)
        if regular or witness: selected.append(row)
    result['classification']='CHRONOS_M3_TIMING_CONTRACT_ESTABLISHED_NO_BASELINE_ADVANTAGE'
    result['paired_identical_success_points']=sum(r['chronos']['success']==r['relative_wait']['success']
                                                for r in result['rows'])
    result['full_metrics']='m3_peer_samples.csv'
    result['selected_witnesses']=selected
    del result['rows']
    # Restart repetition is redundant; keep aggregate plus first and last.
    result['restarts']['selected_witnesses']=[result['restarts']['rows'][0],result['restarts']['rows'][-1]]
    del result['restarts']['rows']


def main():
    run('m3_eventless','test_m3_baseline',extra_sources=['test/m3_eventless.v'])
    run('m3_peer_tb','test_m3_peer',extra_sources=['test/m3_peer_tb.v','test/m3_eventless.v','test/m3_countdown.v'])
    safety=[]
    for width in (8,5):
        parameters=dict(TIME_W=width,DEPTH=1,GEN_W=8,GUARDS_ENABLED=0)
        run('chronos_programmable_core','test_m3_safety',parameters)
        path=ROOT/'build/chronos_programmable_core'/('-'.join(f'{k}{v}' for k,v in parameters.items()))/'m3_safety.json'
        safety.append(json.loads(path.read_text()))
    result=json.loads((ROOT/'build/m3_peer_tb/m3_peer_timing.json').read_text())
    result['restarts']=json.loads((ROOT/'build/m3_peer_tb/m3_restarts.json').read_text())
    result['safety']=safety
    experiment_paths=[ROOT/p for p in ('model/m3_peer.py','model/m3_baseline.py','model/m3_countdown.py',
        'test/m3_peer_tb.v','test/m3_eventless.v','test/m3_countdown.v','test/test_m3_peer.py',
        'test/test_m3_safety.py','scripts/m3_experiment.py','scripts/run_sim.py')]
    result['provenance']=dict(frozen_ancestor='4632d7dec8c533090eff4a70dae565d1cba8b260',
        source_sha256={str(p.relative_to(ROOT)).replace('\\','/'):
            hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'src').glob('*.v'))},
        experiment_sha256={str(p.relative_to(ROOT)).replace('\\','/'):
            hashlib.sha256(p.read_bytes()).hexdigest() for p in experiment_paths},
        tool_versions=dict(iverilog=subprocess.run([os.environ.get('IVERILOG','iverilog'),'-V'],
            capture_output=True,text=True).stdout.splitlines()[0]),
        command='python scripts/m3_experiment.py',physical_campaign=False)
    frozen='4632d7dec8c533090eff4a70dae565d1cba8b260'
    assert not subprocess.run(['git','diff','--exit-code',frozen,'--','src','model/programmable_core.py','model/m2_workloads.py'],cwd=ROOT).returncode
    curate(result)
    (ROOT/'docs/results/m3_peer_timing.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result['aggregate'],indent=2))


if __name__=='__main__':
    main()
