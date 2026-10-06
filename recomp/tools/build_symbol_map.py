#!/usr/bin/env python3
"""
Build the StarCraft: Ghost (Xbox) source-symbol map.

Inputs (all under recomp/build/, regenerated from the user's own files):
  analysis.json          tools.xbe_parser: sections, entry, imports, xdk version
  disasm/functions.json  tools.disasm: every detected function (start/end/section)
  pdb_modules.txt        llvm-pdbutil dump --modules: module -> .obj / .lib
  pdb_files.txt          llvm-pdbutil dump --files: module -> source files
  Ghost.map              the linker MAP (recovered from the game folder directly)

Outputs (recomp/symbols/*):
  ghost.symbols.json     machine-readable map: one entry per function address
  ghost.names.txt        "0xVA name" lines, the shape merge_names --names-json eats
  ghost.sources.txt      "0xVA source_file" lines, for the decomp workflow

Why this exists
---------------
Ghost.xbe shipped next to its linker MAP and its PDB. The MAP's entry point
(found via section:offset) resolves to the XBE entry point 0x001B3FBB, so the
MAP describes *this* XBE -- not the PC build beside it. It carries 24,725 real
symbols, game code included, each tagged with its defining object file. The PDB
maps those objects to their original source paths. Together they give a symbol
source the reference port had to rebuild with Ghidra/IDA; we already have it.

The MAP is parsed here rather than via tools.symbols.map_names because map_names
drops the Lib:Object column, and object attribution is what turns a name into a
source file.
"""

import json
import os
import re
import subprocess
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # recomp/
BUILD = os.path.join(ROOT, "build")
SYMBOLS = os.path.join(ROOT, "symbols")
GAME = os.path.join(os.path.dirname(ROOT), "extracted", "StarCraft Ghost Xbox Finn Hillbilly")

MOD_RE = re.compile(r"^Mod (\d+) \| `(.+?)`:")
OBJ_RE = re.compile(r"^Obj: `(.+?)`:")
FILE_RE = re.compile(r"^- \(no checksum\) (.+)$")
# " 0001:00000000       ?name@@...   00400740 f i vui.obj"
MAP_SYM_RE = re.compile(
    r"^\s*([0-9a-f]{4}):([0-9a-f]{8})\s+(\S+)\s+([0-9a-f]{8})\s+(\S.*?)\s*$", re.I)


def load_sections():
    a = json.load(open(os.path.join(BUILD, "analysis.json")))
    return a, a["sections"]


def parse_map(path, sections):
    """Ghost.map -> {va: (mangled, Lib:Object)}.

    MAP section index N corresponds to XBE section N-1 (imagebld discards the
    PE's preferred base but keeps section order); verified by the entry point.
    """
    sec_va = {}
    for idx, s in enumerate(sections, start=1):
        sec_va[idx] = int(s["virtual_addr"], 16)
    out = {}
    for ln in open(path, encoding="utf-8", errors="replace"):
        m = MAP_SYM_RE.match(ln)
        if not m:
            continue
        idx, off, name, _base, rest = (
            int(m.group(1), 16), int(m.group(2), 16), m.group(3), m.group(4), m.group(5))
        if idx not in sec_va:
            continue
        obj = rest.split()[-1] if rest.split() else ""
        out[sec_va[idx] + off] = (name, obj)
    return out


def parse_modules(path):
    mods, cur = {}, None
    for ln in open(path, encoding="utf-8", errors="replace"):
        m = MOD_RE.match(ln)
        if m:
            cur = int(m.group(1))
            mods[cur] = {"name": m.group(2), "lib": None}
            continue
        m = OBJ_RE.match(ln)
        if m and cur is not None:
            mods[cur]["lib"] = m.group(1)
    return mods


def parse_files(path):
    files, cur = {}, None
    for ln in open(path, encoding="utf-8", errors="replace"):
        m = MOD_RE.match(ln)
        if m:
            cur = int(m.group(1))
            files.setdefault(cur, [])
            continue
        m = FILE_RE.match(ln)
        if m and cur is not None:
            files[cur].append(m.group(1).replace("\\", "/"))
    return files


def obj_source_map(mods, files):
    """object basename (lower) -> best original source path."""
    out = {}
    for mod, meta in mods.items():
        fs = files.get(mod, [])
        if not fs:
            continue
        obj = os.path.basename(meta["name"].replace("\\", "/"))
        stem = os.path.splitext(obj)[0].lower()

        def score(p):
            pl = p.lower()
            base = os.path.basename(pl)
            is_cpp = 1 if pl.endswith((".c", ".cpp", ".cc", ".cxx")) else 0
            named = 1 if (stem and stem in base) else 0
            return (named, is_cpp)

        out[obj.lower()] = max(fs, key=score)
    return out


def batch_demangle(names):
    need = [n for n in names if n.startswith("?")]
    if not need:
        return {}
    proc = subprocess.run(["llvm-undname"], input="\n".join(need) + "\n",
                          capture_output=True, text=True)
    lines = proc.stdout.split("\n")
    out, i = {}, 0
    while i < len(lines):
        mangled = lines[i].strip()
        if not mangled:
            i += 1
            continue
        out[mangled] = lines[i + 1].strip() if i + 1 < len(lines) else ""
        i += 2
        while i < len(lines) and not lines[i].strip():
            i += 1
    return out


def demangled_to_c(demangled, mangled, va):
    """Readable, C-legal identifier: Class::method -> Class_method__VA.

    The demangled string looks like
      "public: virtual void __thiscall cAITerranLightInfantry::Foo(int)"
    We want the declarator only -- `cAITerranLightInfantry::Foo` -- with the
    return type / cv qualifiers dropped, because the name should say *what* the
    function is, not its signature (that lives in `demangled`).
    """
    d = demangled or mangled
    d = re.sub(r"^(public|private|protected):\s*", "", d)
    d = re.sub(r"\b(__thiscall|__cdecl|__stdcall|__fastcall|__vectorcall)\b", "", d)
    # Everything before the argument list is the declarator; take its last token
    # (the qualified function name), e.g. "int  cShell::IsHacking".
    head = d.split("(", 1)[0].strip()
    token = head.split()[-1] if head.split() else d
    if token in ("new", "delete"):
        token = "operator_" + token
    token = token.replace("::", "_")
    token = re.sub(r"<[^>]*>", "", token)          # drop template args
    token = re.sub(r"[^0-9A-Za-z_]", "_", token)
    token = re.sub(r"_+", "_", token).strip("_")
    if not token or token[0].isdigit():
        token = "sub_" + token
    return f"{token}_{va:08X}"


def main():
    os.makedirs(SYMBOLS, exist_ok=True)
    analysis, sections = load_sections()
    map_syms = parse_map(os.path.join(GAME, "Ghost.map"), sections)
    funcs = json.load(open(os.path.join(BUILD, "disasm", "functions.json")))
    mods = parse_modules(os.path.join(BUILD, "pdb_modules.txt"))
    files = parse_files(os.path.join(BUILD, "pdb_files.txt"))
    obj_src = obj_source_map(mods, files)

    print(f"map symbols: {len(map_syms)}  functions: {len(funcs)}  "
          f"modules: {len(mods)}  obj->source: {len(obj_src)}")

    dem = batch_demangle([n for n, _ in map_syms.values()])
    print(f"demangled: {len(dem)}")

    entries = {}
    for f in funcs:
        va = int(f["start"], 16)
        sym = map_syms.get(va)
        e = {"va": f"0x{va:08X}", "end": f["end"], "size": f.get("size"),
             "section": f.get("section"), "detected": True}
        if sym:
            mangled, obj = sym
            e["mangled"] = mangled
            e["demangled"] = dem.get(mangled, "")
            e["name"] = demangled_to_c(e["demangled"], mangled, va)
            basename = os.path.basename(obj.replace("\\", "/")).lower()
            if basename:
                e["object"] = obj
                if basename in obj_src:
                    e["source_file"] = obj_src[basename]
                    e["source_origin"] = "direct"
        else:
            e["name"] = f"sub_{va:08X}"
        entries[e["va"]] = e

    # Source-file interpolation. The linker emits each object file's functions
    # contiguously, so an unattributed run bracketed by two functions that agree
    # on one source file almost certainly belongs to that file too. Only fill
    # when both endpoints agree and live in the same section (different sections
    # are different link units and adjacency means nothing across them). Same
    # rule as tools.debug_symbols; direct evidence always wins.
    ordered = sorted(entries.values(), key=lambda e: int(e["va"], 16))
    known = [i for i, e in enumerate(ordered) if "source_file" in e]
    filled = 0
    for ia, ib in zip(known, known[1:]):
        if ib - ia < 2:
            continue
        a, b = ordered[ia], ordered[ib]
        if a["source_file"] != b["source_file"] or a.get("section") != b.get("section"):
            continue
        for k in range(ia + 1, ib):
            e = ordered[k]
            if "source_file" in e or e.get("section") != a.get("section"):
                continue
            e["source_file"] = a["source_file"]
            e["source_origin"] = "interpolated"
            filled += 1

    named = sum(1 for e in entries.values() if "mangled" in e)
    sourced = sum(1 for e in entries.values() if "source_file" in e)
    total = len(entries)
    coverage = {
        "functions_detected": total,
        "functions_named_from_map": named,
        "functions_with_source_file": sourced,
        "functions_with_source_direct": sum(1 for e in entries.values() if e.get("source_origin") == "direct"),
        "functions_with_source_interpolated": sum(1 for e in entries.values() if e.get("source_origin") == "interpolated"),
        "named_percent": round(100.0 * named / total, 2),
        "sourced_percent": round(100.0 * sourced / total, 2),
        "distinct_source_files": len({e["source_file"] for e in entries.values() if "source_file" in e}),
    }
    meta = {
        "title": analysis["title"], "title_id": analysis["title_id"],
        "xdk_version": analysis["xdk_version"], "build_date": analysis["build_date"],
        "entry_point": analysis["entry_point"], "base_address": analysis["base_address"],
        "map_symbols_total": len(map_syms),
        "source": "Ghost.map (pub+static, with Lib:Object) + Ghost.pdb (modules/files)",
    }

    with open(os.path.join(SYMBOLS, "ghost.symbols.json"), "w") as fh:
        json.dump({"meta": meta, "coverage": coverage, "functions": entries},
                  fh, indent=1)

    ordered = sorted(entries.items(), key=lambda kv: int(kv[0], 16))
    with open(os.path.join(SYMBOLS, "ghost.names.txt"), "w") as fh:
        for va, e in ordered:
            fh.write(f"{va} {e['name']}\n")
    with open(os.path.join(SYMBOLS, "ghost.names.json"), "w") as fh:
        json.dump({va: e["name"] for va, e in ordered}, fh, indent=1)
    with open(os.path.join(SYMBOLS, "ghost.sources.txt"), "w") as fh:
        for va, e in ordered:
            if "source_file" in e:
                fh.write(f"{va} {e['source_file']}\n")

    print(json.dumps(coverage, indent=1))
    print(f"wrote {SYMBOLS}/ghost.symbols.json, ghost.names.txt, ghost.sources.txt")


if __name__ == "__main__":
    main()
