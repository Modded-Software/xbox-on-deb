#!/usr/bin/env python3
"""
Annotate generated recompiled C with the source map.

The lifter already writes a per-function banner:

    /**
     * sub_00012000
     * Original: 0x00012000 - 0x0001201D (29 bytes, 10 insns)
     * Category: game_vtable
     * CC: thiscall, 0 params, returns int_zero
     * Frame: fpo_leaf
     */

This pass enriches it with what only we know -- the real name, the original
source file, the demangled signature, and any hand note for the address -- so a
500k-line tree is greppable by subsystem and a crash stack means something:

    /**
     * cShell_IsHacking_00012000
     * Original: ...
     * Source:   c:/star/code/game/ui/vui.cpp
     * Signature: public: int __thiscall cShell::IsHacking(void)
     * NOTE: gates the hack-system render on two global flags.
     */

Pattern taken from the PSX/PSP recomp projects: generated code stays a build
artifact, and human knowledge lives in a data file (psxrecomp injects
annotations/*.csv the same way), never in a patch.

Usage:
  annotate_gen.py --gen-dir <dir> --functions <functions.json> \
                  [--annotations <annotations.csv>] [--in-place]
"""
import argparse
import csv
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A lifter banner: "/**\n * <name>\n * Original: 0x<VA> ..."
BANNER_RE = re.compile(
    r"(/\*\*\n \* [^\n]*\n \* Original: 0x([0-9A-Fa-f]+)[^\n]*\n)"
)


def load_meta(functions_path):
    out = {}
    for f in json.load(open(functions_path)):
        out[int(f["start"], 16)] = f
    return out


def load_annotations(path):
    notes = {}
    if not path or not os.path.exists(path):
        return notes
    with open(path, newline="") as fh:
        for row in csv.reader(fh):
            if not row or row[0].lstrip().startswith("#"):
                continue
            if len(row) < 2:
                continue
            addr, note = row[0].strip(), row[1].strip()
            if addr.lower() in ("address", "va"):
                continue
            try:
                notes[int(addr, 16)] = note
            except ValueError:
                continue
    return notes


def enrich(text, meta, notes):
    def repl(m):
        va = int(m.group(2), 16)
        f = meta.get(va)
        if not f:
            return m.group(1)
        extra = ""
        if f.get("source_file"):
            extra += f" * Source:    {f['source_file']}\n"
        if f.get("demangled"):
            extra += f" * Signature: {f['demangled']}\n"
        if va in notes:
            extra += f" * NOTE:      {notes[va]}\n"
        return m.group(1) + extra

    return BANNER_RE.sub(repl, text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen-dir", required=True)
    ap.add_argument("--functions", required=True)
    ap.add_argument("--annotations", default=os.path.join(ROOT, "config", "annotations.csv"))
    ap.add_argument("--in-place", action="store_true")
    a = ap.parse_args()

    meta = load_meta(a.functions)
    notes = load_annotations(a.annotations)
    print(f"functions: {len(meta)}  notes: {len(notes)}")

    files = [p for p in sorted(os.listdir(a.gen_dir)) if re.fullmatch(r"recomp_\d+\.c", p)]
    touched = annotated = 0
    for name in files:
        path = os.path.join(a.gen_dir, name)
        text = open(path).read()
        new = enrich(text, meta, notes)
        touched += 1
        if new != text:
            annotated += 1
            if not a.in_place:
                open(path + ".annotated", "w").write(new)
                continue
            open(path, "w").write(new)
    where = "in place" if a.in_place else ".annotated copies"
    print(f"scanned {touched} chunk files, enriched {annotated} -> {where}")


if __name__ == "__main__":
    main()
