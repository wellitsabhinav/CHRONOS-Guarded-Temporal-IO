"""Prepare the pinned CMOS5L timing models for zero-delay Icarus simulation.

No cell logic or UDP tables change. Icarus ignores timing checks and cannot
drive their delayed_* arguments. Remove specify blocks and use actual pins
instead. STA remains the physical timing evidence; this is functional GLS.
"""
import argparse
import hashlib
from pathlib import Path
import re


def prepare(source, output):
    raw = Path(source).read_bytes()
    text = raw.decode("utf-8-sig")
    text = re.sub(r"\bspecify\b.*?\bendspecify\b", "", text, flags=re.S)
    text = re.sub(r"\bwire\s+delayed_\w+\s*(?:,\s*delayed_\w+\s*)*;", "", text)
    text = re.sub(r"\bdelayed_(\w+)\b", r"\1", text)
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("// Zero-delay functional view; source SHA256 " +
                      hashlib.sha256(raw).hexdigest() + "\n" + text)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("output")
    args = parser.parse_args()
    prepare(args.source, args.output)
