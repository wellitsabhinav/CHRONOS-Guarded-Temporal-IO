"""Only real pins and the public snapshot protocol; no hierarchy."""
import cocotb
from cocotb.triggers import Timer
from model.m2_workloads import reactive,uart
from model.programmable_core import encode


class Host:
    def __init__(self,d):
        self.d,self.time=d,0

    async def cycle(self,command=0,nibble=0,gpio=0,reset=False,read=False,ena=True):
        d=self.d
        d.clk.value=0; d.rst_n.value=not reset; d.ena.value=ena
        d.ui_in.value=(128 if read else 0)|(command<<4)|nibble; d.uio_in.value=gpio
        await Timer(5,unit='ns')
        d.clk.value=1
        await Timer(5,unit='ns')
        self.time=0 if reset else self.time+1
        return int(d.uo_out.value)|(int(d.uio_out.value)<<8)|(int(d.uio_oe.value)<<16)

    async def load(self,words):
        await self.cycle(6,0)
        await self.cycle(3)
        for w in words:
            for i in range(8): await self.cycle(1,(w>>(i*4))&15)
            await self.cycle(2)
        origin=self.time
        await self.cycle(7)
        return origin


@cocotb.test()
async def loadable_default_and_snapshot(dut):
    h=Host(dut)
    await h.cycle(reset=True)
    words,input_at,expected=reactive('direct',deadline=30,sample=29)
    origin=await h.load(words)
    while h.time<=origin+34:
        t=h.time
        state=await h.cycle(gpio=1)
        assert state==(0xf0ccaa if t>=origin+30 else 0)
    capture=h.time
    bytes_=[(await h.cycle(4,read=True))&255]
    for _ in range(14): bytes_.append((await h.cycle(5,read=True))&255)
    assert bytes_[0]&3==3 and bytes_[1]==0
    assert int.from_bytes(bytes(bytes_[4:8]),'little')==capture
    assert int.from_bytes(bytes(bytes_[12:15]),'little')==0xf0ccaa
    assert await h.cycle(ena=False)==0
    assert await h.cycle()==0xf0ccaa
    await h.cycle(2)  # incomplete write
    assert (await h.cycle(4,read=True))&128
    await h.cycle(reset=True)
    for _ in range(9): await h.cycle(1,0)
    await h.cycle(2)
    assert (await h.cycle(4,read=True))&128  # overlong word rejected
    await h.cycle(7)
    await h.cycle()  # rejected write left slot zero unwritten
    await h.cycle(4,read=True)
    assert (await h.cycle(5,read=True))&32
    await h.cycle(reset=True)
    await h.load([encode(4),encode(5,30),encode(0)])
    for _ in range(8): await h.cycle(1,0)
    await h.cycle(2)  # halted but sampler still busy: write must reject
    assert (await h.cycle(4,read=True))&0x88==0x88
    await h.cycle(reset=True)
    words,expected=uart()
    origin=await h.load(words)
    latest=0
    for t in range(h.time,origin+61):
        if t-origin in dict(expected): latest=dict(expected)[t-origin]
        assert await h.cycle()==latest
