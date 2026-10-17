#!/usr/bin/env python3
"""Copy the lifted C tree, opening every guest function with RECOMP_PROF_SCOPE.

The profiled build (``PROF=1 bash recomp/game/build.sh``) compiles this copy
instead of ``recomp/game/src/recomp/gen``. Instrumenting a copy rather than
regenerating with ``tools.recomp --trace-functions`` keeps the hand edits in
the in-tree gen/ (see recomp/game/MANUAL_PATCHES.md) and needs no XBE
analysis, so the profiled build is always the same code as the normal one
plus the scope guard.

RECOMP_PROF_SCOPE (refs/xboxrecomp/src/kernel/recomp_prof.h) declares a
cleanup-attributed local: entering pushes a guest shadow-stack frame, every C
return pops it. That gives a per-thread guest call stack (crash, watchdog and
watch reports print it) and an inclusive/self time profile (RECOMP_PROF=1).

Only files whose output changed are rewritten, so an incremental profiled
build recompiles what changed in gen/ and nothing else.

    instrument_gen.py --src recomp/game/src/recomp/gen --dst recomp/build/gen_prof
"""

import argparse
import os
import re
import sys

# Lifted functions are emitted as "void Name_VVVVVVVV(void)\n{\n".
FUNC_RE = re.compile(r"^void (\w+_([0-9A-Fa-f]{8}))\(void\)\n\{\n", re.M)
INCLUDE = '#include "recomp_prof.h"\n'


def instrument(text):
    count = 0

    def sub(m):
        nonlocal count
        count += 1
        name, va = m.group(1), m.group(2)
        return (f"{m.group(0)}    RECOMP_PROF_SCOPE(\"{name}\", 0x{va.upper()});\n")

    out = FUNC_RE.sub(sub, text)
    if count:
        out = INCLUDE + out
    return out, count


def write_if_changed(path, data):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="surrogateescape") as fh:
            if fh.read() == data:
                return False
    with open(path, "w", encoding="utf-8", errors="surrogateescape") as fh:
        fh.write(data)
    return True


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", required=True, help="lifted gen/ directory")
    ap.add_argument("--dst", required=True, help="instrumented output directory")
    args = ap.parse_args(argv)

    os.makedirs(args.dst, exist_ok=True)
    keep = set()
    total = changed = 0
    for name in sorted(os.listdir(args.src)):
        src = os.path.join(args.src, name)
        if not os.path.isfile(src) or not name.endswith((".c", ".h")):
            continue
        keep.add(name)
        with open(src, "r", encoding="utf-8", errors="surrogateescape") as fh:
            text = fh.read()
        n = 0
        if name.endswith(".c"):
            text, n = instrument(text)
        total += n
        if write_if_changed(os.path.join(args.dst, name), text):
            changed += 1
    for name in os.listdir(args.dst):
        if name.endswith((".c", ".h")) and name not in keep:
            os.remove(os.path.join(args.dst, name))
    print(f"instrument_gen: {total} functions instrumented, "
          f"{changed} files rewritten -> {args.dst}")
    if not total:
        print("instrument_gen: ERROR no functions matched", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
