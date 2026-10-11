"""Run small JSON cycle scripts: python -m model.cli examples/m0/basic.json."""

import argparse
import json
from pathlib import Path
from . import Event, GPIOState, TemporalEngine


def integer(value):
    return int(value, 0) if isinstance(value, str) else int(value)


def run_script(script):
    engine = TemporalEngine(script.get("depth", 8), script.get("time_w", 32))
    operations = {}
    for operation in script.get("operations", []):
        at = operation["at"]
        if at in operations or not 0 <= at < script["cycles"]:
            raise ValueError("operations need unique at values within cycles")
        operations[at] = operation
    trace = []
    for cycle in range(script["cycles"]):
        operation = operations.get(cycle, {})
        event = None
        if "timestamp" in operation:
            event = Event(integer(operation["timestamp"]), GPIOState(
                *(integer(operation.get(key, 0)) for key in ("uo", "uio_out", "uio_oe"))))
        result = engine.step(event, reset=operation.get("reset", False),
                             drop=operation.get("drop", False))
        if result.executed:
            state = result.executed.state
            trace.append({"cycle": result.time, "uo": state.uo,
                          "uio_out": state.uio_out, "uio_oe": state.uio_oe})
            print(f"cycle {result.time}: uo=0x{state.uo:02x} "
                  f"uio_out=0x{state.uio_out:02x} uio_oe=0x{state.uio_oe:02x}")
        if result.rejected:
            print(f"cycle {result.time}: request rejected; faults=0x{int(engine.faults):x}")
    print(f"final: time={engine.time} occupancy={len(engine.queue)} "
          f"faults=0x{int(engine.faults):x} epoch_closed={engine.epoch_closed}")
    return trace, engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script", type=Path)
    args = parser.parse_args()
    run_script(json.loads(args.script.read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
