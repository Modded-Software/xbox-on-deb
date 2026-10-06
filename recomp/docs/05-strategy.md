# 05 — Strategy and plan

## Goals

1. **Run Ghost.xbe natively**, not under an emulator, with far better
   performance and without the ~5-minute HLE boot stall.
2. **Keep it readable and maintainable**: every function named from the real
   symbol table, every generated function traceable to its original source file.
3. **Keep all game knowledge as data**, never as a mega-patch. Regeneration must
   be free and repeatable.

## Non-goals / out of scope

- The POSIX OpenGL D3D8 backend. We target **Windows x64** and run under
  **Proton/Steam** (D3D11 → DXVK → Vulkan).
- A Vulkan backend. That is following work.
- Multiplayer / Xbox Live. Leave the network stubs as they are.

## Toolchain decision

| Concern | Choice | Why |
|---|---|---|
| Analysis pipeline | Linux + Python 3.13 + capstone | toolchain-agnostic; already running; produces all our `symbols/` |
| Guest code generation | `tools.recomp` → C | the toolkit's core |
| Compile target | **Windows x64, MinGW-w64** (`refs/xboxrecomp/cmake/mingw-w64-x86_64.cmake`) | avoids MSVC; the D3D11 backend is the complete one |
| Runtime host | **GE-Proton 11-1** (Steam) with the existing `scghost` prefix | DXVK translates D3D11→Vulkan; already installed and tuned |
| Game data | beside `Ghost.exe`, same layout as the XBE drop | file path translation reads it directly |

Fallback if MinGW hits MSVC-specific `recomp_types.h` assumptions: build inside a
Windows VM/container with MSVC. Not expected, but note it.

## Architecture: the D3D8 fork

Decided: **HLE at the D3D8 COM boundary** (`recomp_lookup_manual` redirects
`IDirect3DDevice8` methods into `xbox_d3d8`). The statically linked D3D section is
still disassembled and recompiled (it must be, for function boundaries), but its
GPU work funnels through the runtime's NV2A→D3D11 layer rather than being a full
register-accurate NV2A in guest code. This is the toolkit's mature path and the
one most titles use.

The reference port's hooks into the D3D section
(`0x002C99B0`, `0x002D3D78`, `0x002D2148`, `0x002C99B0`) remain useful as
*bring-up landmarks* and are recorded in `config/fixups.toml`.

## Phased plan

### Phase 0 — Project skeleton (this session)
- `refs/` cloned and gitignored; docs written; source map built.
- **Done-ish.** Remaining: create the game project (CMake) from
  `templates/new-game`, with `XBOXRECCOMP_DIR=refs/xboxrecomp`.

### Phase 1 — Generate and link (smoke)
1. Merge `symbols/ghost.names.txt` into `disasm/functions.json`
   (see [04-source-map.md](04-source-map.md)).
2. Run `tools.recomp` **all sections**, `--split 250`, `--gen-dir src/game/recomp/gen`,
   with `--exclude-manual src/manual/overrides.c`.
3. Cross-compile with MinGW to `Ghost.exe` (Windows x64).
4. Run under GE-Proton with output to a log. **Expect a crash**; that is the
   start, not a failure.

### Phase 2 — Boot to first pixels
Iterate on the crash loop (toolkit `docs/pipeline/06-debugging.md`):
memory layout → kernel init → path translation → bridge → input → APU → NV2A
hooks → `g_esp` → `recomp_dispatch_init()` → guest entry `0x001B3FBB`.
Use the VEH/guest-stack diagnostics from `refs/scghost-recomp/src/main.c`, but in
our own `src/manual/`.
Track fixes in `config/fixups.toml` and overrides in `config/overrides.toml`
(VA → C symbol selected via `recomp_lookup_manual`), i.e. **data, not C**.

### Phase 3 — Menus, then gameplay
Order the bring-up exactly as the reference status table implies: video→menu→
loading→gameplay→audio. For each crash: identify the guest function (our symbol
map names it), decide recompile-vs-override, record it.

### Phase 4 — Fidelity and performance
- Rendering: texture formats, shaders, blend states (the runtime is strong here).
- Audio: XACT engine → APU; DSP effects remain stubbed.
- Bink FMV: decode `.bik` via ffmpeg (or skip cutscenes for first play).
- Performance: the toolkit's recommended dispatch/register-model improvements
  (flat dispatch, per-basic-block entries, real guest return address, TLS-cache
  registers). Adopt in that order, measured.

### Phase 5 — Correctness
- Run the toolkit's **conformance oracle** (`tools/conformance/xbe_run.py`) —
  Xbox code is 32-bit x86 and executable on the host, so the shipped machine code
  is a behavioural reference for the lifted C. This is a rare, cheap correctness
  check; wire our `functions.json` into it.
- Keep the source map fresh as functions get identified.

## Readability mechanics (the explicit ask)

1. **Function names from the MAP** (93.1% already) — via `merge_names --apply`.
2. **A per-function banner** injected into generated C by a post-processor
   (`recomp/tools/annotate_gen.py`, to be written): `// <demangled> — <source_file> (0xVA, N bytes)`.
   Re-runnable after regeneration; never a patch.
3. **Chunk by original source file** where the map knows it — one generated `.c`
   per `.cpp` — instead of opaque 250-function buckets.
4. **A side file the debugger/IDE uses:** `ghost.symbols.json` already maps every
   address, so a crash at host RIP → guest VA → name + source is one lookup.
5. **Manual layer** in `config/annotations.toml` for the functions we actually
   study; merged last, never clobbered.

## Verification strategy

| Layer | Check |
|---|---|
| Lifting | `tools.recomp` unit tests; `recomp_stubs_unresolved.c` must stay small |
| Behaviour | `tools/conformance` runs guest bytes vs lifted C on chosen functions |
| Boot | milestone logs: XBE loaded → memory mapped → kernel init → entry → first present |
| Rendering | screenshot diff against the Cxbx/reference captures |
| Regression | `config/fixups.toml` + `config/overrides.toml` replayed on every regeneration |

## Risks (see 06)

The top three: (a) MinGW build friction with `recomp_types.h`; (b) the D3D fork
being the wrong call for this beta's NV2A usage; (c) the unnamed 1,193 functions
hiding the crash you are chasing. All three have mitigations recorded in
[06-open-questions.md](06-open-questions.md).
