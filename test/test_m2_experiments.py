import json
from pathlib import Path
import cocotb
from test_programmable import Harness
from model.m2_workloads import uart,reactive,cases,summarize


@cocotb.test()
async def measured_protocols(dut):
    h=Harness(dut)
    await h.cycle(reset=True)
    words,expected=uart()
    origin=await h.load(words)
    rows=[]
    while h.m.engine.time <= origin+60:
        rows.append(await h.cycle())
    trace=[(r['time']-origin,r['gpio']) for r in rows if r['executed']]
    assert trace==expected and not h.m.faults
    results=[]
    for case in cases():
        await h.cycle(reset=True)
        words,input_at,expected_at=reactive(case['path'],sample=case['sample'],spacing=case['spacing'],
                                           spi=case['workload']=='spi',absent=case['sample'] is None)
        origin=await h.load(words)
        rows=[]
        while h.m.engine.time<=origin+72:
            rows.append(await h.cycle(input_at(h.m.engine.time-origin,case['value'])))
        result=summarize(case,origin,rows,expected_at(case['value']))
        assert not result['wrong_path']
        assert result['success']==(case['margin'] is not None and case['margin'] >= (2 if case['path']=='reactive' else 1))
        assert result['sample_edges']==([] if case['sample'] is None else [case['sample']])
        if case['workload']=='spi' and result['success']:
            # Peer reads MISO between scheduled falling edges.
            response=0
            for t,state in expected_at(case['value']):
                observed=next(r['gpio'] for r in rows if r['time']-origin==t+case['spacing']//2)
                assert input_at(t,case['value'])&4==0
                assert input_at(t+case['spacing']//2,case['value'])&4
                assert observed==state
                response |= ((observed>>8)&1) << ((t-40)//case['spacing'])
            assert response==(0x9 if case['value'] else 0x6)
            result['peer_response']=response
        results.append(result)
    Path('m2_protocol_experiments.json').write_text(json.dumps(dict(scope='RTL/model every edge; no physical timing',
        uart=dict(byte=0xa6,divisor=4,trace=trace,passed=True),rows=results),indent=2)+'\n')
