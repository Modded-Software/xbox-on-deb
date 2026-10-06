# 00 — Overview and decision

## The decision

Stop emulating `Ghost.xbe` in Cxbx-Reloaded. Statically recompile it to native
code instead.

## Why the emulator is a dead end for this title

- The boot sequence runs the game's own GPU/vsync busy-wait
  (`CMiniport::Isr` polling the emulated NV2A, `rdtsc` pacing) at a very low
  effective frame rate, so the black loading screen takes a constant ~5 minutes.
  This is independent of sound, video files, VSync, render scale and audio
  adapter (all tested; see the repo's `docs/`).
- Cxbx HLEs D3D8/DirectSound at the API boundary, so the game's own (statically
  linked) D3D8 is never executed; every hardware-visible behaviour has to be
  guessed by the emulator. For a beta dev build that pokes the NV2A directly,
  that is the worst case.
- The reference static-recompile port of this exact build already reaches menus,
  gameplay, audio and video. That is evidence the title is tractable this way,
  and the toolkit (`xboxrecomp`) is mature enough to build on.

## What "static recompilation" means here

The `xboxrecomp` toolkit translates every x86 instruction of the XBE into C,
one C function per guest function, and links it against a runtime that
reproduces the Xbox kernel, memory map, D3D8, DirectSound and NV2A *as host
code*. There is no CPU emulator at runtime. The generated C is:

- mechanical and 1:1 with the guest binary (not pretty), and
- **debuggable and modifiable** — this is the property that makes it worth doing
  over an emulator.

Microsoft shipped exactly this for Xbox backwards compatibility ("Ficl/Fission");
see `refs/xboxrecomp/docs/technical/ms-fusion-recompiler.md` for a reverse
engineering of their design, and [docs/05-strategy.md](05-strategy.md) for what
we adopt from it.

## Target build

| Field | Value |
|---|---|
| Title | Starcraft: Ghost (Release) |
| XBE | `Ghost.xbe` |
| Title ID | `0x00000002` |
| Type | **Debug** build (asserts/source names may survive) |
| Build date | 2004-05-08 |
| XDK | 5659 |
| Entry point | `0x001B3FBB` |
| Base address | `0x00010000` |
| Image size | 4.90 MB |
| Sections | 32 (code: `.text`, D3D, D3DX, DSOUND, XACTENG, BINK*, XGRPH, WMADEC, XNET, XPP, DOLBY, BINKDATA) |
| Kernel imports | 137 ordinals |
| Statically linked libs | XAPILIB, D3D8, D3DX8, DSOUND, XACTENG, XBOXKRNL, LIBCMT, LIBC, XGRAPHC, XKBD, XNET |

## The single biggest asset

The release folder includes `Ghost.map` (linker MAP) and `Ghost.pdb` (full debug
symbols) for **this XBE**. That converts the hardest part of a recompilation —
naming and locating functions — from weeks of Ghidra work into a data join. See
[docs/04-source-map.md](04-source-map.md).

## Where the content is

- [01-reference-study.md](01-reference-study.md) — what `aknavj/scghost-recomp`
  and `aknavj/xboxrecomp` are, what they solved, what they got stuck on.
- [02-assets-and-analysis.md](02-assets-and-analysis.md) — every file we have and
  the pipeline output we generated.
- [03-library-and-symbol-catalogue.md](03-library-and-symbol-catalogue.md) —
  kernel and library mapping gaps.
- [04-source-map.md](04-source-map.md) — our symbol/source mapping file and how
  to iterate it.
- [05-strategy.md](05-strategy.md) — the plan, phased, with the readability and
  source-map mechanics.
- [06-open-questions.md](06-open-questions.md) — unknowns and risks.
- [07-decomp-workflow.md](07-decomp-workflow.md) — the readability pipeline
  (names → banners → per-source-file grouping), the annotations file, and the
  matching-decomp path.
