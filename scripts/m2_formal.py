"""Two bounded M2 safety attempts; preserves failures, never claims global proof."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def main():
    summaries=[]
    for name,top,edges,sources in [
        ('dispatcher','reclaim_formal_top',20,['src/chronos_reclaiming_engine.v','formal/reclaim_top.v']),
        ('integrated','programmable_formal_top',20,['src/chronos_reclaiming_engine.v','src/chronos_programmable_core.v','formal/programmable_top.v'])]:
        build=ROOT/'build/m2-formal'/name
        build.mkdir(parents=True,exist_ok=True)
        for source in sources:
            (build/Path(source).name).write_bytes((ROOT/source).read_bytes())
        script='\n'.join(['read_verilog -formal '+' '.join(Path(p).name for p in sources),
                         f'prep -top {top} -flatten','memory_map','opt','dffunmap',
                         'setundef -undriven -anyseq','check -assert',
                         f'sat -seq {edges} -prove-asserts -set-assumes -verify -dump_vcd counterexample.vcd'])+'\n'
        (build/'prove.ys').write_text(script)
        try:
            run=subprocess.run([os.environ.get('YOSYS','yosys'),'-l','formal.log','-s','prove.ys'],
                cwd=build,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,timeout=120)
            status='PASS' if run.returncode==0 else 'FAIL'
            diagnostic=run.stderr[-1000:]
        except subprocess.TimeoutExpired:
            status,diagnostic='TIMEOUT','120-second attempt limit'
        summary=dict(name=name,status=status,edges=edges,time_w=4 if name=='dispatcher' else 5,
            depth=3 if name=='dispatcher' else 2,gpio_w=2,pred_w=1,gen_w=2,diagnostic=diagnostic,
            method='bounded Yosys SAT; initial reset only; arbitrary subsequent inputs/program writes',
            limitation='not unbounded or full-width; arbitrary external token ABA is outside the M2 interface',
            source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources})
        summaries.append(summary)
        print(json.dumps(summary),flush=True)
    (ROOT/'build/m2-formal/summary.json').write_text(json.dumps(summaries,indent=2)+'\n')
    if any(x['status']!='PASS' for x in summaries):
        raise SystemExit('M2 bounded attempt incomplete; inspect preserved diagnostics')


if __name__=='__main__':
    main()
