"""Reproduce the bounded, preregistered gate; no synthesis or physical flow."""
import csv
import hashlib
import json
import os
import subprocess

from run_sim import ROOT,run

FROZEN='df29e14cea7e13489e1b128a590f1f13c3e58681'


def frame_metrics(row,path):
    m=row[path]
    result=[]
    for i,f in enumerate(row['frames']):
        cs=f['cs'];command=cs+40000+f['phase'];release=f['release']
        if release is None:release=cs+380001
        nxt=row['frames'][i+1]['cs'] if i+1<len(row['frames']) else 10**12
        transitions=[v for v in m['transitions'] if cs<=v['t']<nxt]
        decisions=[v for v in m['decisions'] if cs<=v['t']<nxt]
        emissions=[v for v in m['emissions'] if cs<=v['t']<nxt]
        selected=[s for s in m['samples'] if s['frame']==i and s['selected']]
        release_edges=[v['t'] for v in transitions if v['oe']==0 and v['t']>=release] if release!=-1 else []
        sync1=[v['t'] for v in m['states'] if v['t']>=command and (v['sync1']&4)]
        sync2=[v['t'] for v in m['states'] if v['t']>=command and (v['sync2']&4)]
        cs_capture=[v['t'] for v in m['states'] if release!=-1 and v['t']>=release and (v['sync2']&8)]
        idle=[v['t'] for v in m['states'] if release!=-1 and v['t']>=release and not v['active']]
        rearmed=[v['t'] for v in m['states'] if release!=-1 and v['t']>=release and v['armed']]
        first=next((v['t'] for v in transitions if v['oe']),None)
        oe_release=release_edges[0] if release_edges else None
        result.append(dict(frame=i,host_start=f['start'],CS_assert=cs,raw_command=command,
            sync1=next(iter(sync1),None),sync2=next(iter(sync2),None),
            decision=decisions[0]['t'] if decisions else None,first_output=first,
            output_actions=emissions,public_transitions=transitions,
            CS_deassert=release,CS_sync2_capture=next(iter(cs_capture),None),
            OE_deassert=oe_release,descriptor_idle=next(iter(idle),None),
            descriptor_rearm=next(iter(rearmed),None),
            next_command=(nxt+40000+row['frames'][i+1]['phase']) if i+1<len(row['frames']) else None,
            minimum_setup_ps=min((s['setup_ps'] for s in selected),default=None),
            CS_to_command_ps=command-cs,command_to_first_output_ps=first-command if first is not None else None,
            release_latency_ps=oe_release-release if oe_release is not None else None,
            final_sample_to_OE_release_ps=oe_release-(command+320000) if oe_release is not None else None,
            payload_success=m['frames_correct'][i]))
    return result


def curate(result):
    rows=result.pop('rows')
    samples=[];points=[];witnesses=[]
    names={'alternating_16','same_8','autonomous_no_second_START','long_idle','gap_0_rearm_0',
           'gap_10000_rearm_0','gap_30000_rearm_0','CS_release_50000','CS_at_output_-1',
           'CS_at_output_0','CS_at_output_1','missing_SCK_fall','extra_SCK',
           'unsupported_two_command_clocks','missing_CS_release','missing_release_then_next',
           'START_while_response_busy','reset_during_response','reset_before_next',
           'refine_-60001_0','refine_-60000_0','refine_-59999_0'}
    for row in rows:
        point=dict(name=row['name'],group=row['group'],frames=row['frames'])
        for path in ('eventless','relative_wait'):
            m=row[path];fm=frame_metrics(row,path)
            point[path]={k:m[k] for k in ('payload_success','strict_success','unsafe_oe_ps',
                'late_bit_transitions','minimum_selected_setup_ps','frames_correct')}
            point[path]['frame_metrics']=fm
            for sample in m['samples']:
                f=row['frames'][sample['frame']]
                samples.append(dict(case=row['name'],group=row['group'],path=path,
                    host_start=f['start'],CS_assert=f['cs'],raw_command=f['cs']+40000+f['phase'],
                    CS_deassert=f['release'] if f['release'] is not None else f['cs']+380001,
                    **sample))
        points.append(point)
        if row['name'] in names:witnesses.append(row)
    result['classification']='EVENTLESS_SPI_FRAMING_INSUFFICIENT'
    result['baseline_identity']='eventless is the unchanged M3 edge-reactive baseline; one RTL path, two names'
    result['aggregate']={path:{group:dict(cases=sum(r['group']==group for r in rows),
        payload_pass=sum(r[path]['payload_success'] for r in rows if r['group']==group),
        strict_pass=sum(r[path]['strict_success'] for r in rows if r['group']==group))
        for group in ('alignment','refinement','repetition','adversarial')}
        for path in ('eventless','relative_wait')}
    result['points']=points
    result['selected_witnesses']=witnesses
    result['full_samples']='eventless_samples.csv'
    with (ROOT/'docs/results/eventless_samples.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(samples[0]));writer.writeheader();writer.writerows(samples)
    assert any(not r['eventless']['frames_correct'][1] for r in rows if r['name']=='autonomous_no_second_START')
    assert any(r['eventless']['unsafe_oe_ps'] for r in rows if r['group']=='alignment')
    return result


def main():
    frozen_paths=['src','model/m3_baseline.py','model/m3_countdown.py','model/m3_peer.py',
                  'test/m3_eventless.v','test/m3_countdown.v','docs/results/m3_peer_timing.json',
                  'docs/results/m3_peer_samples.csv','docs/results/m2_initial_evaluation.md']
    subprocess.run(['git','diff','--exit-code',FROZEN,'--',*frozen_paths],cwd=ROOT,check=True)
    run('eventless_gate_tb','test_eventless_gate',extra_sources=[
        'test/eventless_gate_tb.v','test/m3_eventless.v','test/m3_countdown.v'])
    result=json.loads((ROOT/'build/eventless_gate_tb/eventless_gate_raw.json').read_text())
    result=curate(result)
    paths=['research/eventless_spi_hypothesis.md','model/eventless_peer.py',
           'test/eventless_gate_tb.v','test/test_eventless_gate.py','scripts/eventless_experiment.py',
           'test/m3_eventless.v','test/m3_countdown.v','model/m3_baseline.py','model/m3_countdown.py']
    result['provenance']=dict(frozen_ancestor=FROZEN,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
        for p in paths},iverilog=subprocess.run([os.environ.get('IVERILOG','iverilog'),'-V'],
            capture_output=True,text=True).stdout.splitlines()[0],
        command='python scripts/eventless_experiment.py',physical_campaign=False,
        same_time_convention='raw updates and peer samples precede internal clock; RTL observed after NBA')
    (ROOT/'docs/results/eventless_gate.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result['aggregate'],indent=2))
    print(result['classification'],result['cases'],result['compared_cycles'])


if __name__=='__main__':main()
