#!/usr/bin/env python3
"""Attribute a runtime log's size to the mechanism that wrote each line.

Every runtime diagnostic prefixes its lines with a tag ("[INPUT]", "[GPU]",
"[PB] desync", ...). Continuation lines (indented, no tag) are charged to the
last tag seen, which is how the watchdog's GS lines and the stack lines under a
[CRASH] end up attributed to the block that printed them.

    logstats.py LOG [--secs N] [--top 40] [--json OUT] [--from B] [--to B]

--secs is the run's wall time; with it the report adds bytes/s and a
projection per hour, which is the number that matters when deciding whether a
mechanism can stay on across many runs.

The diary error counts (FAILED, error, WARN, rejected, unhandled, unsupported,
[PB] desync, [CRASH]) are printed too, so one call covers the diary entry.
"""
import argparse
import json
import re
import sys
from collections import defaultdict

TAG = re.compile(r"^\s{0,2}(\[[A-Za-z0-9_\- ]{1,24}\])")
ERRORS = ["FAILED", "error", "WARN", "rejected", "unhandled", "unsupported",
          "[PB] desync", "[CRASH]"]


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024.0
    return f"{n:.1f} GB"


def analyse(path, start=0, end=-1):
    sizes = defaultdict(int)
    lines = defaultdict(int)
    errors = {e: 0 for e in ERRORS}
    last = "(untagged)"
    total = 0
    with open(path, "rb") as fh:
        pos = 0
        if start > 0:
            fh.seek(start)
            pos = start + len(fh.readline())    # resync to a line boundary
        for raw in fh:
            pos += len(raw)
            if 0 <= end < pos:
                break
            total += len(raw)
            line = raw.decode("utf-8", "replace")
            m = TAG.match(line)
            if m:
                tag = m.group(1)
                # "[GPU-D3D11] tex ..." and "[GPU] presentation" are distinct
                # mechanisms; keep the first word after the tag for the two
                # tags that multiplex several reporters.
                if tag in ("[GPU]", "[PB]", "[KERNEL]", "[APU]"):
                    rest = line[m.end():].strip().split(" ", 1)[0]
                    if rest and rest.isalpha():
                        tag = f"{tag} {rest}"
                last = tag
            elif line.strip() and not line[:1].isspace():
                last = "(untagged)"
            sizes[last] += len(raw)
            lines[last] += 1
            for e in ERRORS:
                if e in line:
                    errors[e] += 1
    return total, sizes, lines, errors


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--secs", type=float, default=0.0)
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--json", default=None)
    ap.add_argument("--from", dest="start", type=int, default=0,
                    help="analyse only from this byte offset (a phase)")
    ap.add_argument("--to", dest="end", type=int, default=-1,
                    help="... up to this byte offset")
    args = ap.parse_args(argv)

    total, sizes, lines, errors = analyse(args.log, args.start, args.end)
    print(f"log: {args.log}")
    print(f"total: {human(total)} ({total} bytes)"
          + (f", {args.secs:.0f} s wall, {human(total / args.secs)}/s, "
             f"{human(total / args.secs * 3600)}/h" if args.secs else ""))
    print(f"{'bytes':>12} {'share':>6} {'lines':>9} {'B/s':>9}  tag")
    for tag, b in sorted(sizes.items(), key=lambda kv: -kv[1])[:args.top]:
        rate = f"{b / args.secs:9.0f}" if args.secs else f"{'-':>9}"
        print(f"{b:12d} {100.0 * b / max(total, 1):5.1f}% {lines[tag]:9d} {rate}  {tag}")
    print("errors: " + "  ".join(f"{k}={v}" for k, v in errors.items()))
    if args.json:
        with open(args.json, "w") as fh:
            json.dump({"log": args.log, "total": total, "secs": args.secs,
                       "tags": sizes, "lines": lines, "errors": errors}, fh,
                      indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
