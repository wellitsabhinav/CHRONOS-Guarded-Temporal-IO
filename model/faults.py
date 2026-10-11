from enum import IntFlag


class Fault(IntFlag):
    NONE = 0
    QUEUE_OVERFLOW = 1
    TIME_ORDER_FAULT = 2
    DEADLINE_MISS = 4
