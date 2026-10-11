"""Curate successful local runs; keep logs, waveforms and PDK files in build/."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build'
OUT=ROOT/'docs/results'


def read(path):
    return json.loads(path.read_text())


def save(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2)+'\n')


def main():
    configs=[]
    for depth,gen,guard in ((1,2,1),(3,2,1),(3,8,0)):
        folder=BUILD/f'chronos_programmable_core/TIME_W16-DEPTH{depth}-GEN_W{gen}-GUARDS_ENABLED{guard}'
        configs.append(read(folder/'m2_differential.json'))
    suites=[]
    for path in sorted(BUILD.glob('**/test_*_results.xml')):
        if not ('test_programmable' in path.name or 'test_m2' in path.name): continue
        tree=ET.parse(path)
        assert not tree.findall('.//failure') and not tree.findall('.//error')
        tests=tree.findall('.//testcase')
        assert tests and not tree.findall('.//skipped')
        suites.append(dict(file=path.relative_to(ROOT).as_posix(),passed=len(tests)))
    assert sum(s['passed'] for s in suites)==19
    default=BUILD/'chronos_programmable_core/TIME_W32-DEPTH8-GEN_W8-GUARDS_ENABLED1'
    save('m2_differential.json',dict(status='PASS',model_tests=5,all_model_regression_tests=70,
        suites=suites,random_configurations=configs,random_cycles=sum(c['cycles'] for c in configs),
        reuse=read(default/'m2_reuse.json'),reduced_generation_reuses_per_configuration=512,
        compared=['PC/instruction/status','time/origin/cursor','entire logical FIFO through hierarchy',
          'GPIO data/OE','predicate active/resolved/value/generation/refcount','sync1/sync2/previous',
          'sampler descriptor/config/actions/token','command outcomes/retire pulses/sticky faults'],
        limits='directed plus three seeds x 600/configuration; not exhaustive full-width verification'))
    folder=BUILD/'chronos_programmable_core/TIME_W16-DEPTH8-GEN_W8-GUARDS_ENABLED1'
    raw=read(folder/'m2_protocol_experiments.json')
    rows=raw['rows']
    groups=[]
    for workload,spacing in (('adversarial',2),('spi',2),('spi',4),('spi',8)):
        for path in ('guarded','reactive','direct'):
            group=[r for r in rows if (r['workload'],r['spacing'],r['path'])==(workload,spacing,path)]
            minimum=min(r['margin'] for r in group if r['success'])
            representative=next(r for r in group if r['success'] and r['margin']==minimum and r['value']==1)
            groups.append(dict(workload=workload,spacing=spacing,path=path,cases=len(group),
                minimum_sample_margin=minimum,minimum_raw_pin_margin=minimum+2,
                outcomes=[dict(margin=m,successes=sum(r['success'] for r in group if r['margin']==m),
                    cases=2) for m in (10,5,3,2,1,0,-1,None)],
                closest_success=representative))
    guard={ (r['workload'],r['spacing'],r['margin'],r['value']):r['success'] for r in rows if r['path']=='guarded'}
    direct={ (r['workload'],r['spacing'],r['margin'],r['value']):r['success'] for r in rows if r['path']=='direct'}
    assert guard==direct and not any(r['wrong_path'] for r in rows)
    save('m2_protocol_experiments.json',dict(status='PASS',classification='CHRONOS_M2_GUARDS_NO_GO_ORDINARY_DEFAULT',
        scope=raw['scope'],cases=len(rows),uart=raw['uart'],groups=groups,
        frontend_delay_clocks=2,guard_and_direct_full_response_outcomes_identical=True,wrong_path=0,
        replay_check='simulation continues to origin+72; commits must match an originally scheduled timestamp and state',
        limitation='SPI-like external stimulus at programmed edges; not a full asynchronous SPI slave or physical timing'))
    throughput=read(folder/'m2_throughput.json')
    throughput['spi']=read(folder/'m2_protocol_throughput.json')
    save('m2_throughput.json',throughput)
    formal=read(BUILD/'m2-formal/summary.json')
    assert all(r['status']=='PASS' for r in formal)
    save('m2_formal.json',dict(results=formal,assumptions=['first edge reset','clock continues',
        'all subsequent reset, input, write/start and raw dispatcher commands arbitrary',
        'no arbitrary delayed external token supported by integrated M2'],
        properties=['FIFO bounds','reference conservation','safe ARM','sampler token ownership',
        'immutable queued actions','reset','due-only GPIO','wrong-path exclusion','retirement without replay'],
        first_attempt=dict(dispatcher='TIMEOUT at 120 seconds',integrated='PASS at 20 edges',
        change='formal observer replaced variable modulo indexing with fixed physical-slot membership'),
        limits='20-edge reduced-instance proofs, no induction, no full-width or analog proof'))
    synth=read(BUILD/'m2-synth/summary.json')
    for result in synth['results'].values():
        for source,digest in result['source_sha256'].items():
            assert hashlib.sha256((ROOT/'src'/source).read_bytes()).hexdigest()==digest
    synth['storage_bits']=dict(m0_queue=448,m1_queue=728,m2_guarded_queue=728,
        m2_ordinary_queue=448,program=512,program_valid=16,
        m2_predicate_generations=32,m2_predicate_flags=12,m2_guarded_reference_counts=16,
        constant_decoder_table_before_optimization=448,
        note='inferred_memory_bits includes the constant decoder ROM; it is not an SRAM capacity or flop total',
        implementation='all mapped into standard-cell flops and multiplexers; no SRAM macros')
    synth['hypothesis']='guard growth beyond twice M1 needs clear protocol benefit; observed benefit absent'
    save('m2_synthesis.json',synth)
    files=['src/chronos_programmable_core.v','src/chronos_reclaiming_engine.v','src/tt_um_chronos_m2.v',
           'model/programmable_core.py','model/m2_workloads.py','model/tests/test_programmable.py',
           'test/test_programmable.py','formal/reclaim_top.v','formal/programmable_top.v']
    files += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT/'test').glob('test_m2_*.py'))]
    files += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT/'scripts').glob('m2_*.py'))]
    save('m2_manifest.json',dict(classification='CHRONOS_M2_GUARDS_NO_GO_ORDINARY_DEFAULT',
        guards_enabled_default=False,physical_campaign_started=False,
        source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},
        commands=['make m2-test','make m2-experiment','make m2-formal',
                  'CHRONOS_LIBERTY=<pinned-liberty> make m2-synth','python scripts/m2_evidence.py']))
    print('PASS: curated M2 evidence and source provenance')


if __name__=='__main__':
    main()
