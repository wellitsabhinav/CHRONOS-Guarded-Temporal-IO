"""TEST-ONLY ordinary, eventless programmable response descriptor.

There is no event queue, timer, timestamp, interpreter, or delay counter.
``step`` models one rising internal clock edge. Decisions read the old
``sync2`` and ``previous`` values, then the synchronizer advances, exactly
as in the frozen M2 frontend. The caller timestamps observations externally.

The descriptor is atomically captured by ``start``. Two full 24-bit GPIO
actions have the same layout as M2: dedicated outputs [7:0], bidirectional
outputs [15:8], and bidirectional output enables [23:16]. A sampled Boolean
selects action ``value ^ invert_sequence[index]``. The first response action
is emitted on the decision edge itself. Subsequent actions follow the
configured synchronized emit edge. For the SPI experiment the first falling
edge is the command-to-response boundary, so it holds bit zero; subsequent
falling edges advance the response. ``hold_first_emit=False`` supports an
ordinary descriptor without that boundary convention.

An armed descriptor may wait while CS is high. After its selected trigger,
synchronized CS high cancels the response and clears OE. The final response
action is held until deselection or restart; no timeout is supplied because
the descriptor contains no temporal deadline. Absence of an emit edge holds
the current bit. This limitation must be included in baseline comparisons.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class EventlessDescriptor:
    action0: int = 0x010000
    action1: int = 0x010100
    # Same M2 fields: mask, expected, edge mode, trigger pin, select enable/pin.
    compare_config: int = 2 | (2 << 8) | (1 << 16) | (2 << 17) | (1 << 20) | (3 << 21)
    # Index zero is the least significant bit: (0, 1, 1, 0).
    invert_sequence: int = 0b0110
    response_length: int = 4
    trigger_rising: bool = True
    emit_pin: int = 2
    emit_rising: bool = False
    hold_first_emit: bool = True

    def __post_init__(self):
        if any(not 0 <= x <= 0xffffff for x in (self.action0, self.action1, self.compare_config)):
            raise ValueError('actions and compare_config must be 24-bit words')
        if not self.compare_config & (1 << 16):
            raise ValueError('eventless descriptor requires edge-trigger mode')
        if not 0 <= self.invert_sequence < 16 or not 1 <= self.response_length <= 4:
            raise ValueError('response requires 1..4 programmable inversion bits')
        if not 0 <= self.emit_pin <= 7:
            raise ValueError('emit pin must select raw GPIO bit 0..7')


class EventlessResponder:
    """Independent behavioral baseline; no output waits for a target time.

    ``armed`` means awaiting a selected trigger; ``active`` means owning the
    response through deselection. ``completed`` is sticky after the final
    action, including after normal deselection, until restart/reset.
    ``bit_index`` names the last emitted action. ``sampled``/``emitted`` and
    ``cancelled`` are per-edge pulses; ``sample_word`` retains the trigger's
    pre-edge synchronized GPIO word. Restart captures the supplied descriptor
    (or the constructor descriptor), discards the response, and zeros output.
    Reset clears all state, including synchronizer stages and prior input.
    Start does not reset the synchronizer, matching M2 program restart.
    """
    def __init__(self, descriptor=None):
        self.program = descriptor or EventlessDescriptor()
        self.reset()

    def reset(self):
        self.sync1 = self.sync2 = self.previous = self.sample_word = 0
        self.gpio_state = self.bit_index = 0
        self.armed = self.active = self.completed = False
        self.sampled = self.emitted = self.cancelled = False
        self.value = False
        self.boundary_pending = False
        self.descriptor = None

    def step(self, gpio=0, *, start=False, reset=False, descriptor=None):
        """Apply raw GPIO before one internal edge and expose post-edge state.

        Only a start captures ``descriptor``; changing it during a response
        has no effect. Reset takes priority over start; start takes priority
        over triggering, response emission, and deselection on the same edge.
        """
        if reset:
            self.reset()
            return
        old_sync = self.sync2
        self.sampled = self.emitted = self.cancelled = False
        if start:
            self.descriptor = descriptor or self.program
            self.gpio_state = self.bit_index = self.sample_word = 0
            self.armed = True
            self.active = self.completed = False
            self.value = False
            self.boundary_pending = False
        elif self.descriptor is not None:
            d = self.descriptor
            config = d.compare_config
            selected = not ((config >> 20) & 1) or not ((old_sync >> ((config >> 21) & 7)) & 1)
            trigger_pin = (config >> 17) & 7
            def edge(pin, rising):
                now, before = (old_sync >> pin) & 1, (self.previous >> pin) & 1
                return now != before and now == int(rising)
            if not selected:
                self.gpio_state &= 0x00ffff
                self.cancelled = self.active and not self.completed
                self.active = False
                self.boundary_pending = False
            elif self.armed and edge(trigger_pin, d.trigger_rising):
                self.armed = False
                self.active = True
                self.value = (old_sync & (config & 255)) == ((config >> 8) & 255)
                self.sample_word = old_sync
                self.sampled = self.emitted = True
                self.bit_index = 0
                self.completed = d.response_length == 1
                self.boundary_pending = d.hold_first_emit
                self._emit()
            elif self.active and not self.completed and edge(d.emit_pin, d.emit_rising):
                if self.boundary_pending:
                    self.boundary_pending = False
                else:
                    self.bit_index += 1
                    self.emitted = True
                    self.completed = self.bit_index == d.response_length - 1
                    self._emit()
        self.previous, self.sync2, self.sync1 = old_sync, self.sync1, gpio & 255

    def _emit(self):
        d = self.descriptor
        choice = int(self.value) ^ ((d.invert_sequence >> self.bit_index) & 1)
        self.gpio_state = d.action1 if choice else d.action0
