"""Reproduce one late-decision experiment plus a stated conceptual baseline."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from model import Event, GPIOState
from model.guarded_engine import GuardedEngine, GuardedFuture, PredicateCommand
from model.temporal_engine import TemporalEngine


def main():
    rows=[]
    # Registered observation at R; branch selects at R+1; producer issues at
    # R+2. M0 admission is strictly future, so the smallest margin is 3.
    # This explicitly chosen instruction-like baseline is not a measured CPU.
    for margin in [20,10,5,2,1,0,-1,None]:
        for value in [False,True]:
            guard=GuardedEngine()
            reactive=TemporalEngine()
            g=GuardedFuture(100,0,1,GPIOState(0x55),GPIOState(0xAA))
            guard.step(g,predicate=PredicateCommand(0,1,arm=True))
            reactive.step()
            resolution=100-margin if margin is not None else None
            while guard.time<=104:
                now=guard.time
                guard.step(predicate=PredicateCommand(0,1,value=value) if now==resolution else None)
                reactive.step(Event(100,GPIOState(0xAA if value else 0x55))
                              if resolution is not None and now==resolution+2 else None)
            rows.append(dict(margin=margin,value=int(value),
                             guarded_trace=[(t,s.packed) for t,s in guard.trace],
                             guarded_faults=int(guard.faults),
                             reactive_trace=[(t,s.packed) for t,s in reactive.trace],
                             reactive_faults=int(reactive.faults)))
    report=dict(deadline=100,baseline="observation R, branch R+1, M0 enqueue R+2; derived, not a CPU benchmark",
                guarded_margin_cycles=1,reactive_margin_cycles=3,saved_cycles=2,
                assumed_clock_mhz=50,saved_ns=40,rows=rows)
    build=ROOT / "build/m1-experiment"
    build.mkdir(parents=True,exist_ok=True)
    (build / "summary.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
