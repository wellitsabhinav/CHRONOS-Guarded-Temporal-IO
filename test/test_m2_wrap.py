import cocotb
from test_programmable import Harness
from model.tests.test_programmable import slice_program


@cocotb.test()
async def final_edge_reset_and_epoch(dut):
    h=Harness(dut)
    for reset_at in (None,28,29,30,31):
        await h.cycle(reset=True)
        origin=await h.load(slice_program(24,23,False))
        assert origin==7
        for t in range(8,32):
            await h.cycle(1,reset=t==reset_at)
        if reset_at is None:
            assert h.m.engine.closed and h.m.engine.gpio==0xf0ccaa
            assert all(p.refs==0 for p in h.m.engine.predicates)
            await h.cycle(start=True)
            assert not h.m.start_accepted
        else:
            assert not h.m.engine.queue and h.m.engine.gpio==0 and h.m.halted
