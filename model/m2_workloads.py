"""Small instruction constructors and experiment fixtures; no compiler."""
from .programmable_core import encode


def uart(byte=0xa6, divisor=4):
    words=[encode(1),encode(1,(1<<24)|1)]
    words += [encode(2,(1<<24)|10),encode(2,10)]
    words += [encode(2,(((byte>>i)&1)<<24)|divisor) for i in range(8)]
    words += [encode(2,(1<<24)|divisor),encode(0)]
    expected=[(10,1),(20,0)]+[(20+(i+1)*divisor,(byte>>i)&1) for i in range(8)]+[(20+9*divisor,1)]
    return words,expected


def reactive(path, deadline=40, sample=39, spacing=2, spi=False, absent=False):
    low,high=(0x010000,0x010100) if spi else (0x0f3355,0xf0ccaa)
    mask=2 if spi else 1
    config=mask | (mask<<8)
    if spi:
        config |= (1<<16)|(2<<17)|(1<<20)|(3<<21)
    elif absent:
        config |= (1<<16)|(2<<17)
    words=[encode(1,low),encode(1,(1<<24)|high),encode(7,config),encode(4)]
    swap=[0,1,1,0] if spi else [0]
    timeout=deadline+1 if sample is None else sample
    if path=='guarded':
        words += [encode(3,(s<<26)|(deadline if i==0 else spacing)) for i,s in enumerate(swap)]
        words += [encode(5,timeout)]
    elif path=='reactive':
        words += [encode(5,timeout)]
        words += [encode(8,(s<<26)|(deadline if i==0 else spacing)) for i,s in enumerate(swap)]
    elif path=='direct':
        words += [encode(9,deadline),encode(5,(1<<26)|timeout)]
        words += [encode(8,(s<<26)|spacing) for s in swap[1:]]
    else:
        raise ValueError(path)
    words += [encode(0)]
    assert len(words)<=16
    def input_at(t,value):
        if spi:
            # Raw SCK rises two synchronizer edges before architectural R.
            sck=sample is not None and t>=sample-2
            if sck and t>=deadline:
                sck=(t-deadline) % spacing >= spacing//2
            return (value<<1) | (4 if sck else 0)
        return value
    def expected(value):
        return [(deadline+i*spacing,high if value^s else low) for i,s in enumerate(swap)]
    return words,input_at,expected


def cases():
    for spi in (False,True):
        for spacing in ((2,4,8) if spi else (2,)):
            for path in ('guarded','reactive','direct'):
                for margin in (10,5,3,2,1,0,-1,None):
                    for value in (0,1):
                        yield dict(workload='spi' if spi else 'adversarial',path=path,spacing=spacing,
                                   margin=margin,value=value,sample=None if margin is None else 40-margin)


def summarize(case,origin,rows,expected):
    trace=[(r['time']-origin,r['gpio']) for r in rows if r['executed']]
    samples=[r['time']-origin for r in rows if r['sampled']]
    valid=set(expected)
    accepted=[r['time'] for r in rows if r['accepted']]
    return dict(**case,success=trace==expected,wrong_path=any(x not in valid for x in trace),
                trace=trace,expected=expected,sample_edges=samples,
                instructions=sum(r['retired'] for r in rows),accepted=len(accepted),
                predicates=sum(r['predicate_accepted'] for r in rows),
                guard_misses=sum(r['guard_missed'] for r in rows),
                stalls=sum(r['stalled'] for r in rows),max_occupancy=max(r['occupancy'] for r in rows),
                final_faults=rows[-1]['faults'],issue_edges=[t-origin for t in accepted])
