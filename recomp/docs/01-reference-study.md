# 01 — Reference study: `scghost-recomp` and `xboxrecomp`

Both are cloned under `refs/` (gitignored). This is everything worth keeping from
them, and what to avoid.

## 1. `aknavj/scghost-recomp` (the existing attempt)

A tiny project (14 files). It is **not** self-contained: it is the game-specific
half of a two-repo setup and requires `aknavj/xboxrecomp` on the
**`impl-scghost`** branch. The default branch of `xboxrecomp` is not a supported
substitute.

Shape:

| File | Role |
|---|---|
| `regen.sh` | runs the toolkit pipeline (xbe_parser → disasm → func_id → abi_analysis → recomp) |
| `patch.sh` | applies `patches/generated.patch` to the generated C after regeneration |
| `src/main.c` | host entry point: load XBE, map memory, init kernel/APU/GPU, call the guest entry |
| `src/recomp_manual.c` | hand-written overrides + ICALL diagnostics |
| `CMakeLists.txt` | Windows/MSVC only, links 6 xboxrecomp libs + d3d11/dxgi/xinput/winmm/dbghelp |
| `patches/generated.patch` | **173 MB, stored in Git LFS** (only the pointer was fetched) |

### What it solved (README status table)

Videos play (minor tearing), menu scene verified, controller verified, loading
screen partial, gameplay runs but renderer failures exit, audio partial,
rendering partial, **performance 10–15 FPS in the debug menu**.

### What it got stuck on

- **Windows-only.** MSVC, Git Bash, `py -3` launcher, D3D11 backend. Nothing here
  builds on Linux as-is.
- **The patch is the workflow.** Regeneration wipes hand-repairs, so all fixes
  live in a 173 MB blob patch that must match the exact toolkit output. This is
  the single biggest maintainability mistake to not copy.
- **Manual overrides are a growing hardcoded list** in `recomp_manual.c`
  (addresses `0x00210FA0`, `0x00359F12`, `0x0035A64F`, `0x0035DB98`,
  `0x0035D763`, `0x0035D7B5`, `0x0035E1B7`, `0x0035EFF8`, `0x00361256`,
  `0x00320890`, `0x00320B70`, `0x00328920`, `0x00328AE0`, `0x00328D30`). We should
  keep overrides in a keyed data file, not C control flow.
- **Game-specific addresses are hardcoded in `main.c`**, discovered by trial:
  - `YOUR_GAME_ENTRY_POINT 0x001B3FBB`
  - `xbox_Nv2aSoftwareMethodHandler(0x002C99B0, 0x002D3D78)` (D3D section)
  - `xbox_Nv2aMirrorFence(0x002D2148, 0x2C, 0x30)`
  - `xbox_Nv2aFrameCounter(0x002D2148, 0x1DE8)`
  - `APU_TRAP_BASE 0xFE800000` … `0xFE830000`
  - `RECOMP_APU_DSP_ACK="gp:0x810"`, `RECOMP_USB_NDP=2`, `RECOMP_XINPUT_SLOT=auto`
  - `RECOMP_AC97_READY=1`, `RECOMP_NV2A_NATIVE_FENCES=1`, `RECOMP_VBLANK=1`
  These are real, reusable findings for *this* title — but note they are in the
  D3D section **because the game's statically linked D3D8 is recompiled and
  driven**, not replaced. That is the architectural fork we must decide on
  (see [05-strategy.md](05-strategy.md)).

### What to copy from it

- The pipeline order in `regen.sh`, and its warning: **disassemble *all* code
  sections, never `--text-only`** — without the XDK sections there are no
  function boundaries there and each function is glued to the next.
- `main.c` as the bring-up skeleton (memory layout → kernel → paths → bridge →
  input → APU → NV2A hooks → `g_esp` → dispatch → entry).
- Its diagnostics: a VEH handler that names the guest function by host RIP
  (dbghelp), scans the guest stack for return addresses, and dumps the ICALL
  ring buffer even when the stack is destroyed.

### What to avoid

- LFS mega-patch as the repair mechanism.
- MSVC/Windows coupling.
- Hardcoded per-function overrides in C rather than data.
- Silent "return success" stubs (`g_esp += 4`) instead of an honest interpreter
  fallback — explicitly called out in the toolkit docs as the wrong move.

## 2. `aknavj/xboxrecomp` (the toolkit)

411 files, ~8 MB. This is the actual engine. Highlights:

### Pipeline tools (`tools/`, Python + capstone, runs anywhere)

| Tool | What it does |
|---|---|
| `xbe_parser` | XBE headers, 32 sections, entry, certificate, 137 kernel imports, XDK version |
| `disasm` | function detection (linear sweep + recursive descent + xrefs), all sections |
| `func_id` | classifies CRT / RenderWare / XDK / game / vtable / stub |
| `abi_analysis` | calling convention (`cdecl`/`stdcall`/`thiscall`), param count, return hint, frame shape |
| `recomp` | the lifter: x86 → C, dispatch table, stubs |
| `split` | per-function disassembly (byte-exact `db` + mnemonics) for hand decomp |
| `symbols/map_names.py` | **MAP → {va:name}**, and name-porting between titles by byte signature |
| `debug_symbols` | mine `__FILE__` strings from a debug build → function→source file |
| `rtti` | MSVC RTTI → class names, vtables, virtual method addresses (none here) |
| `ghidra_naming` / `ida_naming` | optional external naming (2nd choice now: we have a MAP+PDB) |
| `rtti`, `fusion`, `conformance`, `xmv`, `xiso` | extra analysis/verification tools |

`tools/symbols/map_names.py` already names **StarCraft Ghost (XDK 5659)** as a
donor in its own docs — the toolkit author has used this title's MAP before.

### Runtime (`src/`, 6 static libs)

- `xbox_kernel` — memory layout, file I/O, threads, sync, crypto, HAL, object
  manager. The kernel thunk bridge is `kernel_bridge.c` (~378 KB).
- `xbox_d3d8` — D3D8 compat layer → D3D11 (Windows) or OpenGL 3.3
  (`d3d8_gl.c`, Linux).
- `xbox_dsound`, `xbox_apu` (MCPX APU from xemu), `xbox_nv2a` (NV2A register
  handlers + pushbuffer), `xbox_input`.
- A POSIX build exists (`src/platform/win32_compat.*`, `Dockerfile.gcc`,
  `tools/linux/install_deps.sh`) but its graphics path is OpenGL 3.3 and is the
  incomplete half. **We will not use it.** Our host for the *analysis* pipeline is
  Linux (Python + capstone, toolchain-agnostic); our target for the *game* is
  Windows x64 built with MinGW-w64 (`cmake/mingw-w64-x86_64.cmake`) and run under
  Proton/Steam, where D3D11 is translated by DXVK→Vulkan. Vulkan backend work is
  a separate follow-on, not ours.

### Design documents worth reading in full

- `docs/technical/ms-fusion-recompiler.md` — reverse engineering of Microsoft's
  own Xbox static recompiler. The "what we should adopt" list is our roadmap:
  flat directly-indexed dispatch, entry per basic block, push the **real** guest
  return address, record indirect targets and feed them back, cache TLS registers
  per function, a real interpreter fallback instead of silent stubs, per-title
  config instead of hardcoded special cases.
- `docs/technical/gap-analysis.md` — xboxrecomp vs xemu feature matrix (D3D8
  fixed-function, register combiners, vertex microcode, texture unswizzle, APU).
- `docs/technical/lessons-learned.md` — 29 sessions of Burnout 3. Use
  `CreateFileMapping`+`MapViewOfFileEx` for true RAM mirrors (not `VirtualAlloc`),
  global register model, bump allocator, binary-search dispatch, and the "one
  crash at a time" method.
- `docs/DECOMP.md` and `docs/pipeline/04-lifting.md` — the hand-decomp workflow
  (byte-exact split, why x86 must be `db` + comment, behavioural conformance
  oracle).
- `docs/technical/indirect-calls.md` — the hardest 10%, and the ICALL diagnostics.

### Known gaps relevant to us (from `gap-analysis.md`)

- WMA decoder missing (`WMADEC` section) — Ghost has one.
- APU GP DSP effects and EP encode are stubs; 3D positional audio a no-op.
- Xbox Live / network stubbed (`PhyGetLinkState` = no link).
- YUV/cube/volume texture paths partial.

## 3. Net conclusion

Use `xboxrecomp` **as a toolkit and runtime**, build the game project on Linux,
and put all game-specific knowledge into **data files + our own source map**,
not into a giant patch. The reference port proves the title runs; its workflow
proves the workflow does not scale.
