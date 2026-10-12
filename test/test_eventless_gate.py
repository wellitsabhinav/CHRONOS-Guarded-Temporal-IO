"""Raw public oracle plus per-clock differential check of both frozen baselines."""
from dataclasses import asdict
import json
from pathlib import Path

import cocotb
from cocotb.triggers import Timer

from model.eventless_peer import (T,coarse_cases,refinement_cases,repeated_cases,
                                 adversarial_cases)
from model.m3_baseline import EventlessResponder
from model.m3_countdown import CountdownDescriptor,CountdownResponder


class Harness:
    def __init__(self,dut):
        self.d=dut
        self.cycles=0

    async def case(self,case):
        d=self.d
        e,w=EventlessResponder(),CountdownResponder()
        events=case.schedule()
        starts=case.starts()
        resets=set(case.resets)|{0,T,2*T}
        final=max([f.samples[-1] for f in case.frames]+[f.end for f in case.frames]+list(starts))+12*T
        ticks=set(range(0,final+1,T))
        falls=set(range(T//2,final+1,T))
        samples={t:(i,b) for i,f in enumerate(case.frames) for b,t in enumerate(f.samples)}
        times=sorted(ticks|falls|set(events)|set(samples))
        metrics={p:dict(samples=[],transitions=[],decisions=[],emissions=[],states=[],
                        unsafe_oe_ps=0,late_bit_transitions=[],stable_since=0)
                 for p in ('eventless','relative_wait')}
        raw=dict(cs=1,sck=0,mosi=0)
        outputs=dict(eventless=0,relative_wait=0)
        last=0
        elapsed=0
        d.clk.value=0;d.rst_n.value=0;d.start.value=0;d.gpio_in.value=8;d.first_delay.value=8

        def public_observe(t,new_outputs=None):
            nonlocal last
            for p,m in metrics.items():
                if raw['cs'] and (outputs[p]>>16)&1:
                    m['unsafe_oe_ps']+=t-last
                if new_outputs is not None:
                    old,new=outputs[p],new_outputs[p]
                    if ((old^new)&0x010100):
                        m['stable_since']=t
                        m['transitions'].append(dict(t=t,miso=(new>>8)&1,oe=(new>>16)&1))
                        if ((old^new)&0x100) and any(f.release!=-1 and f.end<=t<
                                (case.frames[i+1].cs if i+1<len(case.frames) else final+1)
                                for i,f in enumerate(case.frames)):
                            m['late_bit_transitions'].append(t)
                    outputs[p]=new
            last=t

        for t in times:
            if t>elapsed:
                await Timer(t-elapsed,unit='ps')
                elapsed=t
            public_observe(t)
            raw.update(events.get(t,{}))
            gpio=(raw['cs']<<3)|(raw['sck']<<2)|(raw['mosi']<<1)
            d.gpio_in.value=gpio
            if t in samples:
                frame,bit=samples[t]
                f=case.frames[frame]
                selected=f.release==-1 or t<f.end
                for p,m in metrics.items():
                    out=outputs[p];oe=(out>>16)&1;miso=(out>>8)&1
                    setup=t-m['stable_since']
                    good=(oe==1 and miso==f.expected[bit] and setup>=T) if selected else oe==0
                    m['samples'].append(dict(frame=frame,bit=bit,t=t,expected=f.expected[bit],
                        selected=selected,miso=miso,oe=oe,setup_ps=setup,correct=bool(good)))
            if t in falls:
                d.clk.value=0
            if t in ticks:
                reset=t in resets
                start=t in starts
                d.rst_n.value=int(not reset);d.start.value=int(start)
                if start:d.first_delay.value=starts[t]
                old_sync=e.sync2
                e.step(gpio,start=start,reset=reset)
                w.step(old_sync,start=start,reset=reset,
                       descriptor=CountdownDescriptor(first_delay=starts.get(t,8),spacing=8))
                d.clk.value=1
                await Timer(1,unit='ps');elapsed=t+1
                expected={'e_gpio':e.gpio_state,'w_gpio':w.gpio_state,'sync1':e.sync1,
                    'sync2':e.sync2,'previous':e.previous,'w_previous':w.previous,'w_count':w.wait_count,
                    'w_faults':w.faults}
                for prefix,model,fields in (
                    ('e',e,('armed','active','completed','bit_index','sampled','emitted','cancelled','sample_word')),
                    ('w',w,('active','completed','resolved','bit_index','sampled','emitted','sample_word'))):
                    expected.update({f'{prefix}_{field}':int(getattr(model,field)) for field in fields})
                actual={field:int(getattr(d,field).value) for field in expected}
                assert actual==expected,(case.name,t,actual,expected)
                self.cycles+=1
                public_observe(t,dict(eventless=actual['e_gpio'],relative_wait=actual['w_gpio']))
                for p,model in (('eventless',e),('relative_wait',w)):
                    m=metrics[p]
                    if model.sampled:m['decisions'].append(dict(t=t,word=model.sample_word))
                    if model.emitted:m['emissions'].append(dict(t=t,index=model.bit_index))
                    state=dict(t=t,active=bool(model.active),completed=bool(model.completed),
                               armed=bool(e.armed) if p=='eventless' else None,
                               sync1=e.sync1,sync2=e.sync2,previous=e.previous)
                    if not m['states'] or any(state[k]!=m['states'][-1][k] for k in state if k!='t'):
                        m['states'].append(state)
        public_observe(final)
        for p,m in metrics.items():
            m.pop('stable_since')
            m['payload_success']=all(s['correct'] for s in m['samples'])
            m['strict_success']=m['payload_success'] and not m['unsafe_oe_ps'] and not m['late_bit_transitions']
            m['minimum_selected_setup_ps']=min((s['setup_ps'] for s in m['samples'] if s['selected']),default=None)
            m['frames_correct']=[all(s['correct'] for s in m['samples'] if s['frame']==i) for i in range(len(case.frames))]
        return dict(name=case.name,group=case.group,frames=[asdict(f) for f in case.frames],
                    starts=starts,resets=case.resets,**metrics)


@cocotb.test()
async def bounded_CS_framing_gate(dut):
    h=Harness(dut)
    cases=coarse_cases()+refinement_cases()+repeated_cases()+adversarial_cases()
    rows=[await h.case(case) for case in cases]
    assert not any(r['eventless']['strict_success'] for r in rows if r['group']=='alignment')
    autonomous=next(r for r in rows if r['name']=='autonomous_no_second_START')
    assert autonomous['eventless']['frames_correct']==[True,False,False]
    assert all(next(r for r in rows if r['name']==name)['eventless']['payload_success']
               for name in ('alternating_16','same_8','long_idle'))
    result=dict(clock_ps=T,period_ps=8*T,required_setup_ps=T,cases=len(rows),
                compared_cycles=h.cycles,rows=rows)
    Path('eventless_gate_raw.json').write_text(json.dumps(result,indent=2)+'\n')
