# 04 — The source map

The source map is the file we own and iterate. It is what turns
`sub_000DEAD0` into `cAITerranLightInfantry::ASUpdateCombatYield` + 
`c:/star/code/game/ai/aiclassterranlightinfantry.cpp`, and it is the reason the
generated code can be *read*.

## The asset that makes it possible

`Ghost.map` (the linker MAP) describes **exactly this XBE**: its `entry point at
0001:001a1fbb` resolves, via `xbe_section[0].va (0x12000) + 0x1a1fbb`, to the
XBE header's entry point `0x001B3FBB`. So the MAP's symbol table is trustworthy
for this binary, not just a same-named PC build. Confirmed by
`tools/symbols/map_names.py resolve` (`entry point check: MATCH`).

## Built outputs (`recomp/symbols/`)

| File | Shape |
|---|---|
| `ghost.symbols.json` | the map: `{meta, coverage, functions: {va: entry}}` |
| `ghost.names.txt` | `0xVA name` lines (human/diff-friendly) |
| `ghost.names.json` | `{va: name}` — the exact shape `merge_names.py --names-json` eats |
| `ghost.sources.txt` | `0xVA /path/file.cpp` lines |
| `ghost.source_files.txt` | function-count per source file |
| `ghost.kernel_imports.txt` | ordinal + implemented/missing |
| `ghost.libraries.json` | sections + libraries |

### Entry schema

```json
"0x000DEAD0": {
  "va": "0x000DEAD0",
  "end": "0x000DEF00",
  "size": 176,
  "section": ".text",
  "detected": true,
  "mangled": "?ASUpdateCombatYield@cAITerranLightInfantry@@UAEHXZ",
  "demangled": "public: virtual int __thiscall cAITerranLightInfantry::ASUpdateCombatYield(void)",
  "name": "virtual_int_cAITerranLightInfantry__ASUpdateCombatYield__000DEAD0",
  "object": "aiClassTerranLightInfantry.obj",
  "source_file": "c:/star/code/game/ai/aiclassterranlightinfantry.cpp"
}
```

`name` is what the recompiler emits as the C function name (unique via the
address suffix). `demangled` is the human signature. `source_file` is the
original translation unit.

## How it is built

`recomp/tools/build_symbol_map.py`:

1. Parse `Ghost.map` directly (not via `map_names`, which drops the object
   column). MAP section N ↔ XBE section N-1; `va = section_va[n-1] + offset`.
   Capture `(mangled, Lib:Object)` per symbol. → 24,725 symbols.
2. `llvm-undname` batch-demangles all `?`-names (one call via stdin).
3. `llvm-pdbutil dump --modules/--files` → object basename → best source file
   (prefer the `.cpp` whose stem matches the `.obj`).
4. Join onto `disasm/functions.json` by start address; leave `sub_XXXX` where
   the MAP has no symbol.

Coverage: 16,114 / 17,307 named (93.1%), 8,188 / 17,307 sourced (47.3%), 222
source files. The named-but-not-sourced remainder is the statically linked XDK
code (D3D, DSOUND, …), which has no game source by definition.

## How it plugs into the pipeline

To make the recompiler emit our names, merge them into `functions.json` before
`tools.recomp`:

```bash
.venv-recomp/bin/python refs/xboxrecomp/tools/ghidra_naming/merge_names.py \
  --names-json recomp/symbols/ghost.names.json \
  --functions-json recomp/build/disasm/functions.json --apply
```

`merge_names.py` sanitises and de-duplicates and only overwrites `sub_*`
placeholders.

### Readability beyond function names

Names alone make a 500k-line call graph legible, but we can do better cheaply:

- **Per-function header comments.** A small post-processor over
  `src/game/recomp/gen/*.c` inserts, above each function, a banner with
  `demangled`, `source_file`, `size` and the guest VA, drawn from
  `ghost.symbols.json`. This is a pure text transform, re-runnable after every
  regeneration, so it never becomes a patch.
- **Demangled signatures as declarations.** `recomp_funcs.h` can carry the
  `<demangled>` in a comment beside each prototype, greppable by subsystem.
- **Group generated files by source file**, not just by 250-function chunks:
  emit one `.c` per original `.cpp` where the map knows it. This is the biggest
  single readability win and maps naturally onto a decomp diff.

These are *our* tools, outside the toolkit, regenerated from data — no LFS patch.

## Iterating (layers, in priority order)

1. **Base layer (done).** `Ghost.map` + `Ghost.pdb`.
2. **Cross-build layer.** `GhostU.map` (update build) and `Star_d.pdb`
   (PC debug) name XDK/library functions the primary map missed. Use
   `tools/symbols/map_names.py port` (byte-signature matching, section-scoped)
   between the XBE variants.
3. **CRT/XDK layer.** `tools.func_id` already named 11 CRT functions;
   Ghidra/IDA FidDb (if installed) adds the MSVC runtime helpers.
4. **Class/vtable layer.** Even without RTTI, the vtable scanner found 12,228
   vtable methods and `func_id` groups them. Where a vtable's class is known from
   the map (constructor `??0Class@@`), name the slots `Class::vfuncN`.
5. **Manual layer.** `config/annotations.toml` — human notes keyed by VA, merged
   last, never overwritten by regeneration. This is where we record "this is the
   physics broadphase" without touching C control flow.
6. **Runtime feedback layer.** Record indirect-call targets at runtime and feed
   them back (Microsoft's `VirtualDispatchTraceFiles`; the toolkit's
   `tools/seed_from_log` + `recomp/icall_feedback.py`). Closes the unnamed-thunk
   gap.

## Line numbers

`Ghost.pdb` carries per-module **file lists** but no line records
(`llvm-pdbutil dump -l` is empty for every module), and DIA/`pretty` is
unavailable off Windows. So we recover **file**, not line. If line numbers are
later wanted, the PC debug build's `Star_d.pdb` is the better bet (it is a true
debug PDB), matched by function-body fingerprint against the XBE.

## Regeneration discipline

`build/` and `src/game/recomp/gen/` are always scraped and rebuilt. Nothing
hand-written lives there. Everything we know is in `symbols/` (data) and
`config/` (data) and `src/manual/` (C overrides keyed by VA). That is the
difference from the reference port's 173 MB patch.
