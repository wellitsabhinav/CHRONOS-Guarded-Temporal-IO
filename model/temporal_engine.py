from dataclasses import dataclass
from .event import Event
from .event_queue import EventQueue
from .faults import Fault
from .gpio_state import GPIOState


@dataclass(frozen=True)
class CycleResult:
    time: int  # pre-edge time
    ready: bool
    accepted: bool = False
    rejected: bool = False
    executed: Event | None = None


class TemporalEngine:
    """An event-level specification, not a transcription of circular FIFO RTL.

    step(event) presents one request on one rising edge. enqueue is an alias
    for that clocked operation and therefore also advances time. run(n)
    presents no requests for n edges. Results label the pre-edge time.
    """

    def __init__(self, depth=8, time_w=32):
        if time_w < 1:
            raise ValueError("time_w must be positive")
        self.limit = (1 << time_w) - 1
        self.queue = EventQueue(depth)
        self.reset()

    def reset(self):
        self.time = 0
        self.queue.clear()
        self.gpio = GPIOState()
        self.faults = Fault.NONE
        self.last_accepted = None
        self.epoch_closed = False
        self.trace = []

    @property
    def ready(self):
        retiring = (not self.epoch_closed and self.queue.head is not None
                    and self.queue.head.timestamp <= self.time)
        return len(self.queue) < self.queue.depth or retiring

    def step(self, event: Event | None = None, *, drop=False, reset=False):
        if reset:
            self.reset()
            return CycleResult(0, False)
        if event is not None and event.timestamp > self.limit:
            raise ValueError("timestamp exceeds configured time width")
        now, ready = self.time, self.ready
        executed = None
        accepted = rejected = False
        if not self.epoch_closed and self.queue.head is not None:
            if self.queue.head.timestamp == now:
                executed = self.queue.pop()
                self.gpio = executed.state
                self.trace.append((now, self.gpio))
            elif self.queue.head.timestamp < now:
                self.queue.pop()
                self.faults |= Fault.DEADLINE_MISS

        if event is not None and ready:
            deadline = self.epoch_closed or event.timestamp <= now
            order = self.last_accepted is not None and event.timestamp <= self.last_accepted
            if deadline:
                self.faults |= Fault.DEADLINE_MISS
            if order:
                self.faults |= Fault.TIME_ORDER_FAULT
            rejected = deadline or order
            if not rejected:
                self.queue.append(event)
                self.last_accepted = event.timestamp
                accepted = True
        elif event is not None and drop:
            self.faults |= Fault.QUEUE_OVERFLOW

        if now == self.limit:
            if len(self.queue):
                self.faults |= Fault.DEADLINE_MISS
            self.queue.clear()
            self.epoch_closed = True
        self.time = (now + 1) & self.limit
        return CycleResult(now, ready, accepted, rejected, executed)

    def enqueue(self, event, *, drop=False):
        return self.step(event, drop=drop)

    def run(self, cycles):
        if cycles < 0:
            raise ValueError("cycles must be nonnegative")
        return [self.step() for _ in range(cycles)]
