"""Architectural guarded-future model: ordered deque and named predicates."""
from collections import deque
from dataclasses import dataclass
from .event import Event
from .gpio_state import GPIOState
from .faults import Fault


@dataclass(frozen=True)
class GuardedFuture:
    timestamp: int
    predicate_id: int
    generation: int
    action_false: GPIOState
    action_true: GPIOState


@dataclass(frozen=True)
class Predicate:
    active: bool = False
    generation: int = 0
    resolved: bool = False
    value: bool = False


@dataclass(frozen=True)
class PredicateCommand:
    predicate_id: int
    generation: int
    arm: bool = False
    value: bool = False


@dataclass(frozen=True)
class GuardedResult:
    time: int
    ready: bool
    accepted: bool = False
    rejected: bool = False
    normal_executed: bool = False
    false_executed: bool = False
    true_executed: bool = False
    guard_missed: bool = False
    predicate_accepted: bool = False
    predicate_rejected: bool = False

    @property
    def executed(self):
        return self.normal_executed or self.false_executed or self.true_executed


class GuardedEngine:
    def __init__(self, depth=8, time_w=32, pred_w=2, gen_w=8):
        if min(depth, time_w, pred_w, gen_w) < 1:
            raise ValueError("positive parameters required")
        self.depth = depth
        self.limit = (1 << time_w) - 1
        self.pred_count = 1 << pred_w
        self.gen_limit = (1 << gen_w) - 1
        self.reset()

    def reset(self):
        self.time = 0
        self.queue = deque()
        self.predicates = {i: Predicate() for i in range(self.pred_count)}
        self.gpio = GPIOState()
        self.faults = Fault.NONE
        self.last_accepted = None
        self.epoch_closed = False
        self.trace = []

    @property
    def ready(self):
        retire = (not self.epoch_closed and self.queue
                  and self.queue[0].timestamp <= self.time)
        return len(self.queue) < self.depth or bool(retire)

    def step(self, event=None, *, predicate=None, reset=False, drop=False):
        if reset:
            self.reset()
            return GuardedResult(0, False)
        if event is not None:
            if not 0 <= event.timestamp <= self.limit:
                raise ValueError("timestamp outside configured width")
            if isinstance(event, GuardedFuture):
                self._validate_token(event.predicate_id, event.generation)
        if predicate is not None:
            self._validate_token(predicate.predicate_id, predicate.generation)
        now, ready = self.time, self.ready
        flags = {}
        if not self.epoch_closed and self.queue and self.queue[0].timestamp <= now:
            head = self.queue.popleft()
            if head.timestamp < now:
                self.faults |= Fault.DEADLINE_MISS
            elif isinstance(head, Event):
                self.gpio = head.state
                flags["normal_executed"] = True
            else:
                p = self.predicates[head.predicate_id]
                if p.active and p.resolved and p.generation == head.generation:
                    self.gpio = head.action_true if p.value else head.action_false
                    flags["true_executed" if p.value else "false_executed"] = True
                else:
                    self.faults |= Fault.GUARD_MISS
                    flags["guard_missed"] = True
            if any(flags.get(k) for k in ("normal_executed", "false_executed", "true_executed")):
                self.trace.append((now, self.gpio))
        if event is not None and ready:
            deadline = self.epoch_closed or event.timestamp <= now
            order = self.last_accepted is not None and event.timestamp <= self.last_accepted
            if deadline:
                self.faults |= Fault.DEADLINE_MISS
            if order:
                self.faults |= Fault.TIME_ORDER_FAULT
            flags["rejected"] = deadline or order
            if not flags["rejected"]:
                self.queue.append(event)
                self.last_accepted = event.timestamp
                flags["accepted"] = True
        elif event is not None and drop:
            self.faults |= Fault.QUEUE_OVERFLOW
        if predicate is not None:
            p = self.predicates[predicate.predicate_id]
            if predicate.arm:
                legal = p.generation < self.gen_limit and predicate.generation == p.generation + 1
                updated = Predicate(True, predicate.generation)
            else:
                legal = p.active and not p.resolved and predicate.generation == p.generation
                updated = Predicate(True, p.generation, True, bool(predicate.value))
            legal = legal and not self.epoch_closed
            flags["predicate_accepted"] = bool(legal)
            flags["predicate_rejected"] = not legal
            if legal:
                self.predicates[predicate.predicate_id] = updated
            else:
                self.faults |= Fault.PREDICATE_FAULT
        if now == self.limit:
            if self.queue:
                self.faults |= Fault.DEADLINE_MISS
            self.queue.clear()
            self.epoch_closed = True
        self.time = (now + 1) & self.limit
        return GuardedResult(now, ready, **flags)

    def _validate_token(self, predicate_id, generation):
        if not 0 <= predicate_id < self.pred_count or not 0 <= generation <= self.gen_limit:
            raise ValueError("predicate token outside configured width")
