"""Independent external SPI-like timeline and pin oracle (integer ps)."""
from dataclasses import asdict, dataclass, replace
from math import ceil
from .m2_workloads import reactive
from .programmable_core import encode

CLOCK = 10000  # ps; frequency results are normalized to this simulation clock
CONFIG = 2 | (2 << 8) | (1 << 16) | (2 << 17) | (1 << 20) | (3 << 21)
ACTIONS = (0x010000, 0x010100)
INVERT = (0, 1, 1, 0)


@dataclass(frozen=True)
class PeerPoint:
    name: str = 'nominal'
    period: int = 8 * CLOCK
    phase: int = 1
    start_offset: int = 0
    sample_shift: int = 0
    required_setup: int = 0
    value: int = 1
    deadline: int = 40
    spacing: int = 8
    length: int = 4
    cs_lead: int = 4 * CLOCK
    cs_early: int | None = None
    missing: bool = False
    missing_fall: int | None = None
    extra: bool = False
    reset_at: int | None = None
    trigger_rising: bool = True

    @property
    def first_fall(self):
        return self.deadline * CLOCK + self.phase + self.start_offset

    @property
    def event(self):
        return self.first_fall - self.period // 2

    def program(self):
        words, _, _ = reactive('direct', deadline=self.deadline,
                               sample=self.deadline + 1, spacing=self.spacing, spi=True)
        # Same finite response length for all competitors; no new ISA feature.
        return words[:6+self.length-1]+[encode(0)]

    def timeline(self, end=None):
        """Inputs precede samples, samples precede clock evaluation on ties.

        This defines zero setup as old-data observation, not simulator delta luck.
        A zero-aperture input/clock tie is ideal digital capture, not analog proof.
        """
        e, f = self.event, self.first_fall
        # State snapshots are independently generated from the peer schedule.
        idle = 0 if self.trigger_rising else 4
        changes = [(e-self.cs_lead-2*CLOCK, 8 | (self.value << 1) | idle, 'idle'),
                   (e-self.cs_lead, (self.value << 1) | idle, 'cs_assert')]
        if not self.missing:
            changes.append((e, (self.value << 1) | (4 ^ idle), 'command'))
        for i in range(self.length):
            if i != self.missing_fall:
                changes.append((f+i*self.period, (self.value << 1) | idle, 'fall'))
            changes.append((f+self.period//2+i*self.period, (self.value << 1) | (4 ^ idle), 'rise'))
        if self.extra:
            changes += [(e-CLOCK, (self.value << 1) | 4, 'extra_rise'),
                        (e-CLOCK//2, self.value << 1, 'extra_fall')]
        cs_end = self.cs_early if self.cs_early is not None else f+self.length*self.period
        changes.append((cs_end, 8 | (self.value << 1), 'cs_deassert'))
        events = [(t, 0, 'input', (v, label)) for t, v, label in changes]
        for i in range(self.length):
            events.append((f+self.period//2+i*self.period+self.sample_shift,
                           1, 'sample', i))
        if self.reset_at is not None:
            events += [(self.reset_at, 0, 'reset', True),
                       (self.reset_at+2*CLOCK, 0, 'reset', False)]
        last = max(t for t, _, _, _ in events) + 5*CLOCK if end is None else end
        events += [(t, 2, 'clock', None) for t in range(CLOCK, last+1, CLOCK)]
        return sorted(events, key=lambda x: (x[0], x[1]))


def summarize(point, rows, samples, baseline_rows, baseline_samples,
              wait_rows=(), wait_samples=()):
    """Metrics are diagnostics; success comes exclusively from peer pin samples."""
    expected = [point.value ^ INVERT[i] for i in range(point.length)]
    out = dict(point=asdict(point), expected_bits=expected,
               peer_edges=sum(kind == 'input' and data[1] in ('command','fall','rise','extra_rise','extra_fall')
                              for _, _, kind, data in point.timeline()))
    raw_event = None if point.missing else point.event-(CLOCK if point.extra else 0)
    capture = None if raw_event is None else ceil(raw_event/CLOCK)*CLOCK
    for label, trace, observed in [('chronos', rows, samples),
                                   ('eventless', baseline_rows, baseline_samples),
                                   ('relative_wait',wait_rows,wait_samples)]:
        if not trace:
            continue
        outputs = [r for r in trace if r['emitted']]
        transitions=[]
        previous_gpio=0
        for row in trace:
            if row['gpio'] != previous_gpio:
                transitions.append(row)
            previous_gpio=row['gpio']
        decisions = [r['t'] for r in trace if r['sampled']]
        records = []
        for i, s in enumerate(observed):
            # Include an output at T in diagnostics, although oracle reads old state.
            target = (point.deadline+i*point.spacing)*CLOCK
            action = (next((x for x in outputs if x['t']==target),None) if label!='eventless'
                      else outputs[i] if i < len(outputs) else None)
            commit = None if action is None else action['t']
            # A redundant event is not an externally observed transition.
            o = commit if any(x['t']==commit for x in transitions) else None
            expected_oe = 0 if (point.cs_early is not None and
                                s['t'] >= point.cs_early+3*CLOCK) else 1
            allowed_oe = [0,1] if (point.cs_early is not None and
                point.cs_early <= s['t'] < point.cs_early+3*CLOCK) else [expected_oe]
            observed_oe = s['gpio'] >> 16
            correct = observed_oe in allowed_oe and (
                observed_oe == 0 or ((s['gpio'] >> 8) & 1) == expected[i])
            stable = next((x['t'] for x in reversed(transitions) if x['t'] < s['t']),None)
            records.append(dict(index=i, T=s['t'], expected=expected[i],
                observed=(s['gpio'] >> 8) & 1, oe=s['gpio'] >> 16,
                expected_oe=expected_oe,allowed_oe=allowed_oe,correct=correct,
                requested_O=target, commit_O=commit, O=o,
                timing_error=None if o is None else o-target,
                commit_error=None if commit is None else commit-target,
                stable_since=stable,setup=None if stable is None or not correct else s['t']-stable))
            records[-1]['setup_correct'] = correct and (expected_oe == 0 or (
                stable is not None and s['t']-stable >= point.required_setup))
            records[-1]['response_deadline'] = s['t']-point.required_setup
        r = decisions[0] if decisions else None
        admissions = [x['t'] for x in trace if x.get('accepted')]
        a = admissions[0] if admissions else None
        o = outputs[0]['t'] if outputs else None
        setups = [s['setup'] for s in records if s['setup'] is not None]
        out[label] = dict(success=len(records)==point.length and all(s['setup_correct'] for s in records),
            sampled_bits_correct=len(records)==point.length and all(s['correct'] for s in records),
            samples=records, intended_E=point.event,E=raw_event,stage1=capture,
            stage2=None if capture is None else capture+CLOCK,
            S=None if capture is None else capture+2*CLOCK, R=r, A=a, O=o,
            E_to_S=None if capture is None else capture+2*CLOCK-raw_event,
            S_to_R=None if r is None or capture is None else r-(capture+2*CLOCK),
            R_to_A=None if r is None or a is None else a-r,
            A_to_O=None if a is None or o is None else o-a,
            E_to_O=None if o is None or raw_event is None else o-raw_event,
            E_to_T=observed[0]['t']-raw_event if observed and raw_event is not None else None,
            worst_setup=min(setups) if setups else None,
            average_setup=sum(setups)/len(setups) if setups else None,
            output_times=[x['t'] for x in outputs],
            pin_transitions=[(x['t'],x['gpio']) for x in transitions],
            stale_commits_after_cs=[] if point.cs_early is None else [x['t'] for x in outputs if x['t']>point.cs_early+3*CLOCK],
            final_gpio=trace[-1]['gpio'],
            issue_stalls=sum(x.get('stalled', False) for x in trace),
            max_occupancy=max((x.get('occupancy',0) for x in trace),default=0),
            final_faults=trace[-1].get('faults',0),
            final_sampler_busy=trace[-1].get('sampler_busy',False),
            completion=trace[-1].get('completed',False),
            fault_edges=[(x['t'],x['faults']) for i,x in enumerate(trace)
                         if x.get('faults',0) and (i==0 or x['faults']!=trace[i-1].get('faults',0))])
    return out


def candidates():
    # Coarse-to-fine, not an exhaustive combinatorial campaign.
    phases = (0, 1, CLOCK//4, CLOCK//2, 3*CLOCK//4, CLOCK-1)
    for period in (16, 8, 4, 2, 5, 6, 7):
        for phase in phases:
            for value in (0, 1):
                yield PeerPoint(name='period_phase', period=period*CLOCK,
                                spacing=period, phase=phase, value=value)
    for phase in (-1, 1, CLOCK//2-1, CLOCK//2+1):
        for p in (6, 7, 8):
            yield PeerPoint(name='sync_boundary',period=p*CLOCK,spacing=p,phase=phase)
    p = PeerPoint()
    for offset in (-4*CLOCK, -CLOCK, -1, 1, CLOCK, 4*CLOCK):
        yield replace(p,name='start_offset',start_offset=offset)
    for shift in (-4*CLOCK, -3*CLOCK, -1, 0, CLOCK):
        yield replace(p,name='sampling_position',sample_shift=shift)
    for ppm_ticks in (-100, -1, 1, 100, CLOCK//2):
        yield replace(p,name='period_mismatch',period=p.period+ppm_ticks)
    for length in (1, 2, 4):
        yield replace(p,name='length',length=length)
    for lead in (1, CLOCK, 4*CLOCK):
        yield replace(p,name='cs_lead',cs_lead=lead)
    # Separate peer electrical deadline from logic sampled at its SCK edge.
    # This is a conditional setup contract, not an asserted real device spec.
    for period in (6,8,10):
        for setup in (CLOCK,2*CLOCK,3*CLOCK,4*CLOCK):
            for phase in (1,CLOCK//2,CLOCK-1):
                yield replace(p,name='setup_requirement',period=period*CLOCK,
                              spacing=period,phase=phase,required_setup=setup)
    yield replace(p,name='missing_command',missing=True)
    yield replace(p,name='missing_fall',missing_fall=1)
    yield replace(p,name='extra_edge',extra=True)
    yield replace(p,name='unexpected_cs',cs_early=42*CLOCK)
    yield replace(p,name='reset_near_response',reset_at=39*CLOCK)
    yield replace(p,name='falling_selected_edge',trigger_rising=False)
    # The frozen sampler supports rising triggers only. Drive a falling-command
    # mode explicitly in the RTL test; this is a limitation, never reencode ISA.


def aggregate(results):
    regular=[r for r in results if r['point']['name']=='period_phase']
    groups=[]
    for p in sorted({r['point']['period'] for r in regular}):
        rows=[r for r in regular if r['point']['period']==p]
        entry=dict(period_clocks=p/CLOCK,tested_points=len(rows))
        for path in ('chronos','eventless','relative_wait'):
            good=[r for r in rows if r[path]['success']]
            margins=[r[path]['worst_setup'] for r in good]
            entry[path]=dict(passed=len(good),safe_tested_fraction=len(good)/len(rows),
                worst_setup_clocks=min(margins)/CLOCK if margins else None)
        groups.append(entry)
    return dict(periods=groups,points=len(results),
                pin_samples=sum(len(r['chronos']['samples']) for r in results))
