"""TEST-ONLY ordinary programmable compare plus relative WAIT/actions.

This competitor receives the SAME pre-edge synchronized GPIO word as M2
and the edge-reactive baseline. It adds no synchronizer stage. There is no
absolute clock/time register, event timestamp, event queue, or FIFO. START
captures two full GPIO actions, compare fields, an inversion sequence and
relative WAIT distances. The timer for the first action begins at START,
independently of when the selected rising trigger resolves the comparison.

With START at internal edge zero and first_delay D, the count is loaded with
D-1. Edges 1..D-1 decrement it; edge D attempts the first emission. Reloading
spacing-1 produces subsequent actions at D+i*spacing. The decision must be
available BEFORE an emission edge, so R <= O-1. A same-edge trigger cannot
rescue a missed emission. This competitor deliberately uses the earliest
possible registered comparison and no extra instruction issue latency.

Failure policy: if a scheduled action lacks a registered decision, stop the
descriptor, set sticky faults bit zero, and hold the prior complete GPIO
state. No late action is replayed. CS gates the decision only; as in frozen
ordinary CHRONOS, it does not cancel an already prepared action sequence.
START restarts the descriptor while preserving GPIO/OE and sticky faults.
Reset clears GPIO, comparison history, countdown and faults.
"""
from dataclasses import dataclass

from .m3_baseline import EventlessDescriptor


@dataclass(frozen=True)
class CountdownDescriptor:
    action0: int = 0x010000
    action1: int = 0x010100
    compare_config: int = EventlessDescriptor().compare_config
    invert_sequence: int = 0b0110
    response_length: int = 4
    first_delay: int = 40
    spacing: int = 8

    def __post_init__(self):
        # Reuse the common full-action/edge/select/inversion field validation.
        EventlessDescriptor(self.action0, self.action1, self.compare_config,
                            self.invert_sequence, self.response_length)
        if not all(1 <= distance <= 0xffffff for distance in (self.first_delay, self.spacing)):
            raise ValueError('relative WAIT distances must be positive 24-bit words')


class CountdownResponder:
    """One step per internal edge; ``gpio`` MUST be pre-edge shared sync2.

    ``bit_index`` is the next response action while active, and the final
    action index after completion. ``wait_count`` contains the remaining
    decrement edges before an emission attempt. ``resolved`` retains the
    selected-trigger comparison through completion. ``sampled``/``emitted``
    are per-edge pulses. The caller records all timing externally.
    """
    def __init__(self, descriptor=None):
        self.program = descriptor or CountdownDescriptor()
        self.reset()

    def reset(self):
        self.gpio_state = self.previous = self.sample_word = self.wait_count = 0
        self.bit_index = self.faults = 0
        self.active = self.completed = self.resolved = self.value = False
        self.sampled = self.emitted = False
        self.descriptor = None

    def step(self, gpio=0, *, start=False, reset=False, descriptor=None):
        """Consume shared pre-edge sync2; START is the emission time origin.

        Reset has priority over START. START captures ``descriptor`` (or the
        constructor program), preserves output, and never captures a trigger
        on that same edge. Descriptor input changes without START are ignored.
        """
        if reset:
            self.reset()
            return
        gpio &= 255
        self.sampled = self.emitted = False
        if start:
            self.descriptor = descriptor or self.program
            self.active = True
            self.completed = self.resolved = self.value = False
            self.sample_word = self.bit_index = 0
            self.wait_count = self.descriptor.first_delay - 1
        elif self.active:
            d = self.descriptor
            config = d.compare_config
            old_resolved, old_value = self.resolved, self.value
            selected = not ((config >> 20) & 1) or not ((gpio >> ((config >> 21) & 7)) & 1)
            rising = (gpio & ~self.previous) & (1 << ((config >> 17) & 7))
            if not old_resolved and selected and rising:
                self.resolved = True
                self.value = (gpio & (config & 255)) == ((config >> 8) & 255)
                self.sample_word = gpio
                self.sampled = True
            if self.wait_count:
                self.wait_count -= 1
            elif not old_resolved:
                self.active = False
                self.faults |= 1
            else:
                choice = int(old_value) ^ ((d.invert_sequence >> self.bit_index) & 1)
                self.gpio_state = d.action1 if choice else d.action0
                self.emitted = True
                if self.bit_index == d.response_length - 1:
                    self.active = False
                    self.completed = True
                else:
                    self.bit_index += 1
                    self.wait_count = d.spacing - 1
        self.previous = gpio
