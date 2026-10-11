"""One apples-to-apples CMOS5L mapping; no P&R or trustworthy timing claim."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def main():
    lib=Path(os.environ['CHRONOS_LIBERTY'])
    yosys=os.environ.get('YOSYS','yosys')
    results={}
    for name,top,guard in [('m0','chronos_engine',None),('m1','chronos_guarded_engine',None),
                           ('m2_guarded','chronos_programmable_core',1),('m2_ordinary','chronos_programmable_core',0),
                           ('m2_wrapper','tt_um_chronos_m2',0)]:
        build=ROOT/'build/m2-synth'/name
        build.mkdir(parents=True,exist_ok=True)
        sources=[top+'.v'] if guard is None else ['chronos_reclaiming_engine.v','chronos_programmable_core.v']
        if top=='tt_um_chronos_m2': sources += [top+'.v']
        for source in sources:
            (build/source).write_bytes((ROOT/'src'/source).read_bytes())
        (build/'cells.lib').write_bytes(lib.read_bytes())
        script=['read_verilog '+' '.join(sources)]
        if guard is not None: script += [f'chparam -set GUARDS_ENABLED {guard} {top}']
        script += [f'hierarchy -check -top {top}', 'proc', 'tee -o storage.json stat -json',
                   f'synth -top {top} -flatten -noabc','dfflibmap -liberty cells.lib','abc -liberty cells.lib',
                   'clean','read_liberty -lib cells.lib','check -assert','tee -o stat.json stat -json -liberty cells.lib']
        (build/'map.ys').write_text('\n'.join(script)+'\n')
        subprocess.run([yosys,'-l','synth.log','-s','map.ys'],cwd=build,check=True,stdout=subprocess.DEVNULL)
        design=json.loads((build/'stat.json').read_text())['design']
        storage=json.loads((build/'storage.json').read_text())['design']
        cells=design['num_cells_by_type']
        result=dict(cells=design['num_cells'],area_um2=design['area'],
            flops=sum(n for c,n in cells.items() if any(s in c for s in ('dff','dfr','sdf'))),
            inferred_memory_bits=storage.get('num_memory_bits',0),mapped_memories=design.get('num_memories',0),
            cell_types=cells,source_sha256={s:hashlib.sha256((ROOT/'src'/s).read_bytes()).hexdigest() for s in sources})
        results[name]=result
        print(name,result['cells'],result['area_um2'],result['flops'],flush=True)
    summary=dict(scope='paired mapped cores; wrapper separate; no routing/CTS/STA',
        tool=subprocess.check_output([yosys,'-V'],text=True).strip(),
        liberty_sha256=hashlib.sha256(lib.read_bytes()).hexdigest(),time_w=32,depth=8,gpio_w=24,pred_w=2,gen_w=8,
        results=results,cost_screen=dict(floorplan_um2=902417,budget_um2=902417*.6,
            doubled_wrapper_um2=2*results['m2_wrapper']['area_um2'],
            passed=2*results['m2_wrapper']['area_um2']<=902417*.6,
            guarded_core_over_2x_m1=results['m2_guarded']['area_um2']>2*results['m1']['area_um2']),
        timing_estimate=None,timing_limitation='mapping does not establish 50 MHz timing')
    (ROOT/'build/m2-synth/summary.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':
    main()
