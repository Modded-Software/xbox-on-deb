# 02 — Assets on hand and analysis output

Everything under `extracted/StarCraft Ghost Xbox Finn Hillbilly/` (gitignored).
This drop is far richer than the XBE alone.

## Builds

| File | Bytes | What it is |
|---|---|---|
| `Ghost.xbe` | 4,280,320 | **Our target.** Xbox debug build, XDK 5659, entry `0x001B3FBB`. |
| `Ghost.map` | 2,700,592 | MSVC linker MAP for `Ghost.xbe` (entry matches). 24,725 symbols. |
| `Ghost.pdb` | 14,109,696 | Full PDB for `Ghost.xbe`. Types, globals, publics, per-module source files. |
| `Ghost.exe` | 5,382,784 | A PC PE build of the same source (for cross-reference, not our target). |
| `GhostR.xbe` / `GhostR.exe` | 3.99 / 5.09 MB | Another Xbox/PC build (variant). |
| `GhostU.xbe` / `GhostU.exe` / `GhostU.map` | 3.75 / 4.83 MB | "Update" build (variant); its MAP is a second symbol donor. |
| `Star.exe` / `Star_d.exe` / `Star_u.exe` | | PC builds. `Star_d.pdb` (11.7 MB) is the **debug** PC build's symbols. |
| `update.xbe` | 2,387,968 | Title-update XBE. |
| `vc60.pdb` / `vc70.pdb` | | VC6/VC7 private PDBs referenced by the toolchain. |

Why the variants matter: `GhostR`/`GhostU`/`Star*` are the same source compiled
with (probably) different optimisation, so function bodies differ. They are
**cross-references for reading code**, not address donors. `GhostU.map` is a
second symbol donor for the XDK library sections (`map_names.py port`).

## Game data

- `c:/star/code/...` source tree names recovered from the PDB (222 files).
- `Sounds/` (`.xsb`/`.xwb` XACT banks), `Video/` (`.bik`/`.vid`), `UI/`,
  `Misc/`, `VertexShaders/` (`.xvu`/`.xpu`/`.ps`), `nsidsp.bin`, `dsstdfx.bin`.

## Pipeline output we generated (`recomp/build/`, gitignored)

Command log and the exact scripts are in [../README.md](../README.md). Results:

| Artifact | Result |
|---|---|
| `analysis.json` | 32 sections; 137 kernel imports; libraries XAPILIB/D3D8/D3DX8/DSOUND/XACTENG/XBOXKRNL/LIBCMT/LIBC/XGRAPHC/XKBD/XNET @ 5659 |
| `disasm/summary.json` | **17,307 functions**, 1,168,971 instructions, 211,228 xrefs, 919 kernel calls, 4,998 strings |
| `disasm/functions.json` | per-function start/end/section/detection/calls/callers |
| `func_id/summary.json` | 14,547 game-classified, 12,228 vtable methods, 11 CRT signatures, 8,891 unknown |
| `abi/abi_functions.json` | 17,307 ABI entries, **4,393 detected `thiscall`** (C++ heavy) |
| `rtti.json` | **no RTTI** (compiled out) — normal for this era |
| `debug_symbols.json` | 25 `__FILE__` source strings → 222 functions attributed (asserts mostly compiled out) |
| `ghost_map_symbols.json` | 24,725 resolved symbols (via `tools/symbols/map_names.py resolve`) |
| `pdb_sections.txt` | 51,078 section contributions (module ↔ address range) |
| `pdb_modules.txt` | 1,063 modules → `.obj`/`.lib` |
| `pdb_files.txt` | 2,312 lines: module → original source files |
| `Ghost_pdb_summary` + `pdb_section_headers.txt` | PDB has Debug Info, Types, Globals, Publics |

### Function detection by section

| Section | Functions | Notes |
|---|---:|---|
| `.text` | 14,882 | game + CRT + statically linked XDK |
| D3D | 297 | statically linked D3D8 |
| D3DX | 441 | |
| DSOUND | 480 | |
| XACTENG | 337 | audio engine |
| BINK | 124 | RAD video |
| WMADEC | 146 | Windows Media Audio decoder |
| XNET | 305 | Xbox Live / networking |
| XPP | 238 | USB/XInput controller (XID/XPP) |
| XGRPH | 36, DOLBY 1, BINKDATA 2, BINK* small | |

### Coverage of our source map (`symbols/ghost.symbols.json`)

| Metric | Value |
|---|---|
| Detected functions | 17,307 |
| Named from `Ghost.map` | **16,114 (93.1%)** |
| Tied to a source file (direct) | 8,188 |
| Tied to a source file (interpolated) | 879 |
| **Tied to a source file (total)** | **9,067 (52.4%)** |
| Distinct source files | **222** |
| Unnamed functions | 1,193 (1,132 in `.text`) |

Source interpolation: the linker emits each object's functions contiguously, so
an unattributed run bracketed by two functions that agree on one source file is
attributed to that file (same rule as `tools.debug_symbols`, guarded by section).
That adds 879 functions over direct object→source joins.

Top source files by function count: `ai/aiclass.cpp` (293),
`sim/simphysics.cpp` (239), `sim/simcontrol.cpp` (235),
`ui/vuiconsole.cpp` (211), `ai/aiclassbasewalker.cpp` (200), … — the whole
game subsystem tree.

### Full generation (first pass)

`tools.recomp --all --split 250` on the named database:

- **17,308 functions translated, 0 failed, 2,202,842 lines of C** across 70
  chunk files; grouped to 223 source-file units. ~87 MB each form.
- **215 unresolved call targets** stubbed (`recomp_stubs_unresolved.c`) — called
  but not detected as functions; these are the first seeds for
  `--coalesce-functions` and for runtime ICALL feedback.
- **238 unimplemented instructions** (36 mnemonics). 104 are hardware/privileged
  — `in`/`out` port I/O and `cli`/`sti`/`int`/`int1` — and 94 of those sit in
  code sections. The rest are decode noise from data-heavy sections decoded as
  code (BINK tables). Full list: `symbols/ghost.unimplemented.txt`.

## Notes on PDB tooling on Linux

`llvm-pdbutil` (LLVM 18) works for `--modules`, `--files`, `--section-contribs`,
`--section-headers`. `--publics` and `--globals` **segfault** in this build
(known LLVM bug); we do not need them because `Ghost.map` is the public-symbol
source. `diadump`/`pretty` need DIA (MSVC) and are unavailable. `llvm-undname`
batch-demangles symbols from stdin — used by `build_symbol_map.py`.
