#!/usr/bin/env python3
"""
Apply our source map onto the recompiler's functions.json.

The toolkit's merge_names.py filters and rewrites names; we want an exact,
transparent application: every address in ghost.symbols.json that is a detected
function gets its name (and its source file / demangled signature as *extra*
fields, which tools.recomp ignores but our post-processor and crash symbolizer
use).

Usage:
  apply_symbol_map.py [--functions PATH] [--symbols PATH] [--no-backup]
"""
import argparse
import json
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_FUNCS = os.path.join(ROOT, "build", "disasm", "functions.json")
DEFAULT_SYMBOLS = os.path.join(ROOT, "symbols", "ghost.symbols.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--functions", default=DEFAULT_FUNCS)
    ap.add_argument("--symbols", default=DEFAULT_SYMBOLS)
    ap.add_argument("--no-backup", action="store_true")
    a = ap.parse_args()

    sym = json.load(open(a.symbols))["functions"]
    funcs = json.load(open(a.functions))

    if not a.no_backup and not os.path.exists(a.functions + ".orig"):
        shutil.copy2(a.functions, a.functions + ".orig")

    named = sourced = 0
    for f in funcs:
        va = f["start"]
        e = sym.get(va)
        if not e or "name" not in e:
            continue
        f["name"] = e["name"]
        named += 1
        if "demangled" in e:
            f["demangled"] = e["demangled"]
        if "source_file" in e:
            f["source_file"] = e["source_file"]
            sourced += 1

    json.dump(funcs, open(a.functions, "w"), indent=1)
    print(f"functions: {len(funcs)}  named: {named}  sourced: {sourced}")
    print(f"wrote {a.functions}")


if __name__ == "__main__":
    main()
