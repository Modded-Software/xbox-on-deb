# 07 — Decomp workflow and generated-code conventions

This is the practical, repeatable pipeline that turns `Ghost.xbe` into readable,
source-attributed C and keeps it that way. Everything here is a build artifact
plus data; nothing is hand-patched.

## The readability layer (three cheap passes)

Raw `tools.recomp` output is correct but anonymous and uniform. Three passes fix
that, in order:

1. **Names** — `tools/apply_symbol_map.py` writes our source map onto
   `functions.json`, so the lifter emits
   `cAITerranLightInfantry_ASUpdateCombatYield_000DEAD0` instead of
   `sub_000DEAD0`. (N64Recomp does the same thing from its symbol file.)
2. **Banners** — `tools/annotate_gen.py` enriches each function's header block
   with the **original source file**, the **demangled signature**, and any
   **hand note** for that address.
3. **Grouping** — `tools/group_by_source.py` reassembles the 250-function
   compiler chunks into **one C file per original `.cpp`**, so the tree mirrors
   the game's own source layout.

Result, verbatim from the probe:

```c
/**
 * cShell_IsHacking_00012000
 * Original: 0x00012000 - 0x0001201D (29 bytes, 10 insns)
 * Source:    c:/star/code/game/ui/vui.cpp
 * Signature: public: int __thiscall cShell::IsHacking(void)
 * NOTE:      cShell::IsHacking - gates hack-system rendering on two instance flags.
 * Category: game_vtable
 * CC: thiscall, 0 params, returns int_zero
 * Frame: fpo_leaf
 */
void cShell_IsHacking_00012000(void) { ... }
```

## Commands

```bash
# after the analysis pipeline has produced build/disasm/functions.json
.venv-recomp/bin/python recomp/tools/build_symbol_map.py        # -> symbols/
.venv-recomp/bin/python recomp/tools/apply_symbol_map.py        # names onto functions.json
# generate (all sections), then readability passes
refs/xboxrecomp -> python -m tools.recomp <xbe> --all --split 250 --functions ... --gen-dir build/gen
.venv-recomp/bin/python recomp/tools/annotate_gen.py --gen-dir build/gen --functions build/disasm/functions.json --in-place
.venv-recomp/bin/python recomp/tools/group_by_source.py --gen-dir build/gen --functions build/disasm/functions.json --out-dir build/gen_by_source
```

Compile **either** `gen/*.c` (chunked, for fast incremental builds) **or**
`gen_by_source/*.c` (grouped, for reading). Never both — duplicate symbols.

## The annotations file

`config/annotations.csv` is `address,note`, injected as `NOTE:` lines by the
annotator. This is the same device PSXRecomp uses (`annotations/*.csv` →
`/* [NOTE] ... */` in generated C), and the same idea as N64Recomp's per-function
entries in its config TOML. It is where human understanding accumulates without
ever touching generated code. Current seeds include the entry point, the D3D
miniport method the reference port hooks, the NV2A fence address, and the kernel
thunk base.

## What the generated C still is (and is not)

It is a **faithful, literal translation**, not decompiled C. Expect:

- guest registers as globals (`eax`, `ecx`, …, `esp`),
- `MEM32(ecx + 0x6DF0)` for field access (no struct types),
- verbose, explicit flag bookkeeping (`_fa/_fb/_fas/_fbs`) on comparisons,
- `loc_XXXX` labels and `goto`, one `goto` per guest branch.

Touching the flag bookkeeping would break guest semantics; we do not rewrite it.
The remainder is best left to the compiler, and read with the banner context.

## Making selected functions truly readable (matching decomp)

For functions we actually study, use the toolkit's decomp path
(`docs/DECOMP.md`): `tools.split` emits byte-exact per-function `.s` files (bytes
as `db`, mnemonics as comments), and the behavioural oracle
(`tools/conformance`) runs the shipped machine code against candidate C. Workflow:

1. Pick a function from `ghost.symbols.json` (it already has name + source).
2. Split it, write clean C, verify with the conformance harness.
3. Register it as an override in `config/overrides.toml` (VA → our C), selected
   by `recomp_lookup_manual` — data, not a patch.

This is how a `Class::method` becomes a genuinely readable function, one at a
time, without forking the lifter.

## Class layouts / types — the current blocker

The single biggest remaining readability gain would be struct types, turning
`MEM32(ecx + 0x6DF0)` into `this->m_foo`. It needs the PDB's TPI type stream.

- `Ghost.pdb` is a 2004 VC7.1-era PDB; its TPI version is **V70**, which LLVM 18
  refuses (`Unsupported TPI Version`). `--publics`/`--globals` also segfault, and
  DIA (`pretty`/`diadump`) needs Windows.
- The MODULE/FILES/SECTION-CONTRIBS streams we *do* read are enough for function
  names and source-file attribution, which is why the source map works anyway.
- Ways to unblock types, in order of effort:
  1. Run a Windows PDB reader (`cvdump`/`dia2dump`) under our GE-Proton Wine —
     these handle old TPI versions. Needs the tool binary.
  2. A minimal V70 TPI reader for our own use (the record layout is documented by
     LLVM; V70 vs V80 differs mainly in the header version and a few leaf
     encodings).
  3. Infer layouts from the map's constructor names (`??0Class@@`) plus the
     constructor bodies — heavy, last resort.

Until then, field offsets are documented per-function via `annotations.csv`.

## Prior art this follows

| Project | Convention we borrow |
|---|---|
| N64Recomp | symbol metadata drives emitted names; config TOML for stubs/patches |
| psxrecomp | generated C is a build artifact; address→note CSV injected as comments; `_full.c` + `_dispatch.c` split |
| psprecomp | per-function banner with instruction/byte counts; per-instruction disassembly comments |
| recomp projects generally | never hand-edit generated C; all knowledge in data/config |
