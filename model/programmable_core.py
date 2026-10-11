"""Independent M2 architecture: deque events, owned tokens and program steps."""
from collections import deque
from dataclasses import dataclass, replace

PROGRAM_FAULT, SAMPLER_FAULT = 32, 64


@dataclass(frozen=True)
class Action:
    timestamp: int
    false: int
    true: int = 0
    guarded: bool = False
    pid: int = 0
    generation: int = 0


@dataclass(frozen=True)
class Allocation:
    active: bool = False
    generation: int = 0
    resolved: bool = False
    value: bool = False
    refs: int = 0


class ReclaimingEngine:
    def __init__(self, depth=8, time_w=32, pred_w=2, gen_w=8, guards=True):
        self.depth, self.limit = depth, (1 << time_w)-1
        self.npred, self.genmax = 1 << pred_w, (1 << gen_w)-1
        self.guards = guards
        self.reset()

    def reset(self):
        self.time = self.gpio = self.faults = 0
        self.queue = deque()
        self.predicates = [Allocation() for _ in range(self.npred)]
        self.last = None
        self.closed = False
        self.pulses = {}

    @property
    def ready(self):
        return len(self.queue) < self.depth or bool(
            not self.closed and self.queue and self.queue[0].timestamp <= self.time)

    def step(self, event=None, command=None, holds=(), reset=False, drop=False):
        if reset:
            self.reset()
            return
        now, before, ready = self.time, list(self.predicates), self.ready
        pulse = dict(accepted=False, rejected=False, executed=False, normal_executed=False,
                     false_executed=False, true_executed=False, guard_missed=False,
                     predicate_accepted=False, predicate_rejected=False)
        if not self.closed and self.queue and self.queue[0].timestamp <= now:
            a = self.queue.popleft()
            p = before[a.pid]
            if a.guarded:
                self.predicates[a.pid] = replace(self.predicates[a.pid], refs=p.refs-1)
            if a.timestamp < now:
                self.faults |= 4
            elif not a.guarded:
                self.gpio = a.false
                pulse['normal_executed'] = pulse['executed'] = True
            elif p.active and p.resolved and p.generation == a.generation:
                self.gpio = a.true if p.value else a.false
                pulse['true_executed' if p.value else 'false_executed'] = True
                pulse['executed'] = True
            else:
                self.faults |= 8
                pulse['guard_missed'] = True
        if event is not None and ready:
            deadline = self.closed or event.timestamp <= now
            order = self.last is not None and event.timestamp <= self.last
            token_bad = event.guarded and (not self.guards or not before[event.pid].active
                        or before[event.pid].generation != event.generation)
            self.faults |= (4 if deadline else 0) | (2 if order else 0) | (16 if token_bad else 0)
            pulse['rejected'] = deadline or order or token_bad
            if not pulse['rejected']:
                self.queue.append(event)
                self.last = event.timestamp
                pulse['accepted'] = True
                if event.guarded:
                    p = self.predicates[event.pid]
                    self.predicates[event.pid] = replace(p, refs=p.refs+1)
        elif event is not None and drop:
            self.faults |= 1
        if command is not None:
            pid, gen, arm, value = command
            p = before[pid]
            nextgen = 1 if p.generation == self.genmax else p.generation+1
            same_push = pulse['accepted'] and event.guarded and event.pid == pid
            good = not self.closed and (
                (p.refs == 0 and pid not in holds and not same_push and gen == nextgen)
                if arm else (p.active and not p.resolved and p.generation == gen))
            pulse['predicate_accepted'], pulse['predicate_rejected'] = good, not good
            if good:
                current = self.predicates[pid]
                self.predicates[pid] = (Allocation(True, gen, refs=current.refs) if arm
                    else replace(current, resolved=True, value=bool(value)))
            else:
                self.faults |= 16
        if now == self.limit:
            if self.queue:
                self.faults |= 4
            self.queue.clear()
            self.predicates = [replace(p, refs=0) for p in self.predicates]
            self.closed = True
        self.time = (now+1) & self.limit
        self.pulses = pulse


class ProgrammableCore:
    def __init__(self, depth=8, time_w=32, pred_w=2, gen_w=8, guards=False):
        self.engine = ReclaimingEngine(depth, time_w, pred_w, gen_w, guards)
        self.program = [0]*16
        self.reset()

    def reset(self):
        self.engine.reset()
        self.valid = [False]*16
        self.pc = self.origin = self.cursor = self.config = self.core_faults = 0
        self.actions = [0, 0]
        self.halted = True
        self.sync1 = self.sync2 = self.previous = self.sample_word = 0
        self.sampler = None
        self.sampled = self.instruction_retired = self.stalled = False
        self.start_accepted = self.write_accepted = False

    @property
    def ready(self):
        return self.halted and not self.engine.queue and self.sampler is None and not self.engine.closed

    @property
    def faults(self):
        return self.engine.faults | self.core_faults

    @property
    def instruction(self):
        return self.program[self.pc] if self.valid[self.pc] else 0

    def step(self, gpio=0, *, write=None, start=False, reset=False):
        if reset:
            self.reset()
            return
        e, now = self.engine, self.engine.time
        old_sync = self.sync2
        control_ready = self.ready
        self.sampled = self.instruction_retired = self.stalled = False
        self.start_accepted = self.write_accepted = False
        event = command = None
        holds = () if self.sampler is None else (self.sampler['pid'],)
        direct = False
        if self.sampler:
            s = self.sampler
            selected = not ((s['config'] >> 20) & 1) or not ((old_sync >> ((s['config'] >> 21) & 7)) & 1)
            edge = (old_sync & ~self.previous) & (1 << ((s['config'] >> 17) & 7))
            trigger = bool(edge) if (s['config'] >> 16) & 1 else now == s['at']
            if trigger and selected and now <= s['at']:
                value = (old_sync & (s['config'] & 255)) == ((s['config'] >> 8) & 255)
                command = (s['pid'], s['generation'], False, value)
                self.sample_word, self.sampled = old_sync, True
                if s['direct']:
                    event = Action(s['deadline'], s['actions'][int(value)])
                    direct = True
                self.sampler = None
            elif now >= s['at']:
                self.core_faults |= SAMPLER_FAULT
                self.sampler = None
        def fault(bit=PROGRAM_FAULT):
            self.core_faults |= bit | PROGRAM_FAULT
            self.halted = True
        def retire():
            self.instruction_retired = True
            if self.pc == 15:
                fault()
            else:
                self.pc += 1
        if write is not None or start:
            if not control_ready:
                fault()
            elif write is not None:
                address, word = write
                self.program[address] = word
                self.valid[address] = True
                self.write_accepted = True
                if start:
                    fault()
            else:
                self.pc = 0
                self.origin = self.cursor = now
                self.actions, self.config = [0, 0], 0
                self.halted = False
                self.start_accepted = True
        elif not self.halted:
            w = self.instruction
            op, arg, pid = w >> 28, w & 0xfffffff, (w >> 24) & 3
            masks = [0, 0x1ffffff, 0x1ffffff, 0x7ffffff, 3, 0x7ffffff,
                     7, 0xffffff, 0x7ffffff, 0xfffffff]
            if not self.valid[self.pc] or op > 9 or arg & ~masks[op] or e.closed:
                fault()
            elif op == 0:
                self.halted = True
                self.instruction_retired = True
            elif op == 1:
                self.actions[(w >> 24) & 1] = w & 0xffffff
                retire()
            elif op == 7:
                self.config = arg
                retire()
            elif op == 9:
                target = self.cursor + arg
                if target > e.limit:
                    fault()
                else:
                    self.cursor = target
                    retire()
            elif op in (4, 6):
                pid = w & 3
                if pid >= e.npred:
                    fault()
                elif command is not None:
                    self.stalled = True
                else:
                    p = e.predicates[pid]
                    if op == 4:
                        if p.refs or pid in holds:
                            self.stalled = True
                        else:
                            gen = 1 if p.generation == e.genmax else p.generation+1
                            command = (pid, gen, True, False)
                            retire()
                    elif not p.active or p.resolved:
                        fault()
                    else:
                        command = (pid, p.generation, False, bool(w & 4))
                        retire()
            elif op == 5:
                at = self.origin + (w & 0xffffff)
                if pid >= e.npred or not e.predicates[pid].active or e.predicates[pid].resolved or at > e.limit or at <= now:
                    fault()
                elif holds:
                    self.stalled = True
                else:
                    self.sampler = dict(pid=pid, generation=e.predicates[pid].generation,
                        at=at, config=self.config, direct=bool(w & (1 << 26)),
                        deadline=self.cursor, actions=tuple(self.actions))
                    retire()
            else:
                target = self.cursor + (w & 0xffffff)
                if target > e.limit or target <= now or (e.last is not None and target <= e.last):
                    fault(4 if target <= now or target > e.limit else 2)
                elif op in (3, 8) and (pid >= e.npred or not e.predicates[pid].active or (op == 3 and not e.guards)):
                    fault(16)
                elif direct or not e.ready or (op == 8 and not e.predicates[pid].resolved):
                    self.stalled = True
                else:
                    swap = (w >> 26) & 1
                    if op == 2:
                        event = Action(target, self.actions[(w >> 24) & 1])
                    elif op == 3:
                        event = Action(target, self.actions[swap], self.actions[swap ^ 1], True,
                                       pid, e.predicates[pid].generation)
                    else:
                        event = Action(target, self.actions[int(e.predicates[pid].value) ^ swap])
                    self.cursor = target
                    retire()
        e.step(event, command, holds, drop=direct)
        if direct and not e.pulses['accepted']:
            self.core_faults |= SAMPLER_FAULT
        if self.sampled and e.pulses['predicate_rejected']:
            self.core_faults |= SAMPLER_FAULT
        if e.closed:
            self.sampler = None
            self.halted = True
        self.previous, self.sync2, self.sync1 = old_sync, self.sync1, gpio & 255


def encode(op, arg=0):
    if not 0 <= op <= 15 or not 0 <= arg < (1 << 28):
        raise ValueError('instruction field overflow')
    return (op << 28) | arg
