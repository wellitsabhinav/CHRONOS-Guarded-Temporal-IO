"""Default-width nonzero generation rollover and 32-bit cursor overflow."""
import json
from pathlib import Path
import cocotb
from test_programmable import Harness
from model.tests.test_programmable import slice_program
from model.programmable_core import encode


@cocotb.test()
async def default_width_reuse_and_arithmetic(dut):
    h=Harness(dut)
    await h.cycle(reset=True)
    await h.load(slice_program(12,11))
    for i in range(512):
        while not h.m.ready: await h.cycle(i&1)
        assert not h.m.faults and h.m.engine.predicates[0].generation==i%255+1
        if i!=511: await h.cycle(start=True)
    assert sum(r.get('executed',False) for r in h.rows)==512
    await h.cycle(reset=True)
    await h.load([encode(9,0xfffffff)]*16)
    while not h.m.halted: await h.cycle()
    assert h.m.faults&32 and h.m.cursor==h.m.origin+15*0xfffffff
    Path('m2_reuse.json').write_text(json.dumps(dict(cycles=512,time_w=32,gen_w=8,depth=8,
        default_generation_rollovers=2,wrong_path=0,cursor_overflow_rejected=True),indent=2)+'\n')
