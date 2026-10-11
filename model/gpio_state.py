from dataclasses import dataclass


@dataclass(frozen=True)
class GPIOState:
    uo: int = 0
    uio_out: int = 0
    uio_oe: int = 0

    def __post_init__(self):
        if any(not 0 <= value <= 255 for value in (self.uo, self.uio_out, self.uio_oe)):
            raise ValueError("GPIO fields must be bytes")

    @property
    def packed(self):
        return self.uo | (self.uio_out << 8) | (self.uio_oe << 16)

    @classmethod
    def unpack(cls, value):
        if not 0 <= value < (1 << 24):
            raise ValueError("GPIO state must fit 24 bits")
        return cls(value & 255, (value >> 8) & 255, value >> 16)
