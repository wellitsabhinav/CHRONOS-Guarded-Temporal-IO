from collections import deque


class EventQueue:
    """Behavioral queue; deliberately has no RTL pointers or memory addresses."""

    def __init__(self, depth):
        if depth < 1:
            raise ValueError("depth must be positive")
        self.depth = depth
        self._events = deque()

    def __len__(self):
        return len(self._events)

    @property
    def head(self):
        return self._events[0] if self._events else None

    @property
    def contents(self):
        return tuple(self._events)

    def append(self, event):
        if len(self) >= self.depth:
            raise ValueError("queue capacity exceeded")
        self._events.append(event)

    def pop(self):
        return self._events.popleft()

    def clear(self):
        self._events.clear()
