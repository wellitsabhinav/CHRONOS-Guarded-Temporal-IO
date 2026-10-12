"""Independent raw peer schedules; no DUT state participates in scheduling."""
from dataclasses import dataclass, field
import math

T = 10_000  # ps; all evidence is normalized to this internal clock


@dataclass
class Frame:
    cs: int
    value: int = 0
    phase: int = 1
    release: int | None = None
    start: int | None = None
    missing_fall: int | None = None
    missing_command: bool = False
    extra: bool = False
    unsupported: bool = False

    @property
    def command(self):
        return self.cs + 4*T + self.phase

    @property
    def samples(self):
        return [self.command + (8+8*i)*T for i in range(4)]

    @property
    def end(self):
        return self.release if self.release is not None else self.cs + 38*T + 1

    @property
    def expected(self):
        return [self.value, self.value ^ 1, self.value ^ 1, self.value]


@dataclass
class Case:
    name: str
    frames: list[Frame]
    resets: list[int] = field(default_factory=list)
    group: str = 'adversarial'

    def schedule(self):
        """Assignments are raw pad values; samples occur even on missing edges."""
        events = {}
        def put(t, **values):
            events.setdefault(t, {}).update(values)
        for f in self.frames:
            put(f.cs, cs=0, sck=0, mosi=f.value)
            if not f.missing_command:
                put(f.command, sck=1)
            for i in range(4):
                if f.missing_fall != i:
                    put(f.command+(4+8*i)*T, sck=0)
                put(f.samples[i], sck=1)
            if f.extra:
                put(f.command+5*T, sck=1)
                put(f.command+6*T, sck=0)
            if f.unsupported:
                # A second command clock: this descriptor has no opcode grammar.
                put(f.command+T, sck=0)
                put(f.command+2*T, sck=1, mosi=f.value ^ 1)
                put(f.command+3*T, sck=0)
            if f.release != -1:
                put(f.end, cs=1)
        return events

    def starts(self):
        return {f.start: max(1, math.ceil((f.command+4*T)/T)-f.start//T)
                for f in self.frames if f.start is not None}


def single(name, delta=0, phase=1, value=0, **kwargs):
    start = 40*T
    return Case(name, [Frame(start+delta, value, phase, start=start, **kwargs)])


def coarse_cases():
    return [Case(f'delta_{d}_phase_{p}_value_{v}',
                 single('', int(d*T), p, v).frames, group='alignment')
            for d in (-8,-6,-4,-2,-1,-.5,0,.5,1,2,4,6,8)
            for p in (0,1,T//2,T-1) for v in (0,1)]


def refinement_cases():
    # Local boundary R=START and R=START+1, plus adjacent half/whole clocks.
    return [Case(f'refine_{d}_{v}', single('', d, 0, v).frames, group='refinement')
            for d in (-7*T,-65000,-6*T-1,-6*T,-6*T+1,-55000,-5*T-1,-5*T,-5*T+1)
            for v in (0,1)]


def train(name, count=2, gap=4*T, rearm=3*T, phase=1, alternating=True,
          autonomous=False, release_phase=1):
    frames=[]
    cs=40*T
    for i in range(count):
        start = 36*T if i==0 else None if autonomous else math.ceil((frames[-1].end+rearm)/T)*T
        frames.append(Frame(cs, i%2 if alternating else 1, phase,
                            release=cs+38*T+release_phase, start=start))
        cs=frames[-1].end+gap
    return Case(name,frames,group='repetition')


def repeated_cases():
    cases=[train('alternating_16',16),train('same_8',8,alternating=False),
           train('autonomous_no_second_START',3,autonomous=True),
           train('long_idle',2,gap=80*T)]
    for gap in (0,T//2,T,2*T,3*T,4*T):
        for rearm in (0,T,2*T,3*T):
            cases.append(train(f'gap_{gap}_rearm_{rearm}',gap=gap,rearm=rearm))
    for rp in (0,T//2,T-1):
        cases.append(train(f'release_phase_{rp}',release_phase=rp))
    for gap in (T-1,T+1):
        cases.append(train(f'gap_capture_boundary_{gap}',gap=gap,rearm=0))
    for offset in (-T,-1,0,1,T,2*T):
        c=train(f'rearm_at_final_capture_{offset}',gap=4*T)
        # Old final sample C+2 is around CS+39 for phase=1.
        c.frames[1].start=(c.frames[0].samples[-1]+T-1)//T*T+2*T+offset
        # Host START remains a clocked control: snap non-clock offsets down.
        c.frames[1].start=c.frames[1].start//T*T
        cases.append(c)
    return cases


def adversarial_cases():
    s=40*T
    cases=[]
    # CS release before capture, within response and around final emit.
    for offset in (3*T,4*T+1,5*T,16*T,32*T-1,32*T,32*T+1,36*T+2,48*T):
        cases.append(single(f'CS_release_{offset}',release=s+offset))
    cases += [single('missing_CS_release',release=-1),
              single('missing_command',missing_command=True),
              single('missing_SCK_fall',missing_fall=1),
              single('missing_final_fall',missing_fall=3),
              single('extra_SCK',extra=True),
              single('unsupported_two_command_clocks',unsupported=True)]
    short=single('short_CS_between_clocks',delta=1,release=s+T//2)
    cases.append(short)
    busy=train('START_while_response_busy',2,gap=4*T)
    busy.frames[1].start=s+20*T
    cases.append(busy)
    reset=single('reset_during_response')
    reset.resets=[s+18*T]
    cases.append(reset)
    reset_next=train('reset_before_next',2)
    reset_next.resets=[reset_next.frames[1].start-T]
    cases.append(reset_next)
    # No release separating frames, with a host restart inside held-low CS.
    no_release=train('missing_release_then_next',2)
    no_release.frames[0].release=-1
    cases.append(no_release)
    # +/-1 ps around a real synchronized intermediate output (CS+18 clocks).
    for epsilon in (-1,0,1):
        cases.append(single(f'CS_at_output_{epsilon}',release=s+18*T+epsilon,phase=0))
    return cases
