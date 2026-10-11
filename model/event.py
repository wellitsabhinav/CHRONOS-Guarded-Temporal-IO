from dataclasses import dataclass
from .gpio_state import GPIOState


@dataclass(frozen=True)
class Event:
    timestamp: int
    state: GPIOState

    def __post_init__(self):
        if self.timestamp < 0:
            raise ValueError("timestamp must be nonnegative")

    @property
    def word(self):
        """Default top-level loader word: time low, GPIO high."""
        if self.timestamp >= (1 << 32):
            raise ValueError("loader timestamp exceeds 32 bits")
        return self.timestamp | (self.state.packed << 32)
