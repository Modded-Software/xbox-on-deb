# 03 — Library and symbol catalogue

A mechanical catalogue of what the binary needs from the runtime and what is
already covered. Generated data lives in `recomp/symbols/`:
`ghost.kernel_imports.txt`, `ghost.libraries.json`, `ghost.source_files.txt`.

## 1. Kernel imports (137) vs the xboxrecomp bridge

Cross-checked against `refs/xboxrecomp/src/kernel/kernel_thunks.c`
(`xbox_resolve_ordinal` switch) and `kernel_bridge.c`.

**Result: 136 / 137 covered. Missing: 1.**

| Ordinal | Name | Status |
|---:|---|---|
| 37 | `FscSetCacheSize` | **MISSING** — file-system cache size. Trivial stub (return success). |

Full list: `symbols/ghost.kernel_imports.txt`.

Groups (as parsed by `xbe_parser`):

| Group | Count | Notable |
|---|---:|---|
| Ke | 24 | timers, DPCs, events, `KeQueryPerformanceCounter`, `KeStallExecutionProcessor` |
| Nt | 25 | file I/O, events, virtual memory, `NtDeviceIoControlFile` |
| Rtl | 13 | strings, critical sections, `RtlUnwind` (SEH) |
| Mm | 12 | contiguous/pool memory, `MmGetPhysicalAddress`, `MmClaimGpuInstanceMemory` |
| Xc | 11 | SHA/RC4/HMAC/RSA/DES (save + signature) |
| Xbox | 10 | `XboxHardwareInfo`, `XeLoadSection`, keys, `XePublicKeyData` |
| Hal | 10 | `HalReadWritePCISpace`, video mode, shutdown, SMC |
| Io | 10 | device/IRP plumbing (DVD) |
| Ex | 5, Av 4, Kf 2, Ob 2, Ps 2, Other 7 |  |

Data exports among these (`XboxHardwareInfo`, `XboxKrnlVersion`, `KeTickCount`,
`LaunchDataPage`, keys, `HalDisk*`) are handled by `kernel_data_va_for_ordinal`
in `kernel_bridge.c`.

**Action:** add one stub for ordinal 37, then the kernel gap list is empty.

## 2. Statically linked XDK libraries

The XBE carries the Xbox SDK libraries **linked into its own image**, as separate
code sections. These are not kernel imports; they are recompiled guest code.

| Section | VA | Size | Functions | Runtime counterpart in xboxrecomp |
|---|---|---:|---:|---|
| `.text` | `0x0012000` | 2.81 MB | 14,882 | game + CRT (`LIBCMT`/`LIBC`) + XAPI |
| `D3D` | `0x02C04A0` | 81 KB | 297 | `xbox_d3d8` (D3D8→D3D11/GL) and `xbox_nv2a` |
| `D3DX` | `0x02D4960` | 115 KB | 441 | (D3DX helpers; no runtime equivalent — recompiled) |
| `DSOUND` | `0x02F16A0` | 121 KB | 480 | `xbox_dsound` + `xbox_apu` |
| `XACTENG` | `0x030FCA0` | 43 KB | 337 | `xbox_dsound`/`xbox_apu` at the engine boundary |
| `BINK` + BINK* variants | `0x031AB00`… | ~90 KB | ~140 | **none** — RAD Game Tools FMV; needs a decoder |
| `XGRPH` | `0x032FFC0` | 8.6 KB | 36 | (XG* graphics helpers) |
| `WMADEC` | `0x03322E0` | 100 KB | 146 | **missing in xboxrecomp** (`gap-analysis.md`) |
| `XNET` | `0x034B360` | 56 KB | 305 | stubbed (Xbox Live: "no link") |
| `XPP` | `0x03593A0` | 33 KB | 238 | bypassed by `xbox_input` (XInput) |
| `DOLBY` | `0x04C9F80` | 28 KB | 1 | APU (xemu) partial |

Plus data sections `$ $XTIMAGE`, `$ $XSIMAGE`, `.XTLID`, `BINKDATA`, `.rdata`,
`.data`.

### The architectural fork (important)

Xbox's D3D8 is **statically linked into the game**. Two ways to run it:

1. **Recompile it verbatim** (Microsoft's approach in Ficl/Fission): the guest
   D3D8 executes and talks to a hardware-accurate NV2A at the register/pushbuffer
   level. The reference port leans this way — that is why `main.c` hooks
   addresses inside the game's own `D3D` section (`0x002C99B0` method handler,
   `0x002D3D78`, `0x002D2148` fence).
2. **HLE at the D3D8 API boundary**: `recomp_lookup_manual` redirects each
   `IDirect3DDevice8` method to `xbox_d3d8`'s D3D11/GL layer. This is what most
   xboxrecomp titles do.

The reference port appears to do a hybrid. Decision (see
[05-strategy.md](05-strategy.md)): **use (2), the D3D8→D3D11 HLE backend, build
for Windows (x64), and run it under Proton/Steam.** The POSIX OpenGL backend is
**out of scope** — it is the incomplete path and we do not want to maintain it.
A Vulkan backend is follow-on work and not part of this effort. D3D11 under
Proton is served by DXVK→Vulkan at runtime, which is a supported, well-tested
stack (we already run GE-Proton for the emulator).

## 3. Symbol naming coverage

| Source | Yield |
|---|---|
| `Ghost.map` publics + statics | **24,725 symbols** |
| → matching detected functions | 16,114 (93.1%) |
| `Ghost.pdb` object → source | 8,188 functions, **222 source files** |
| `tools.debug_symbols` (`__FILE__`) | 222 functions (asserts mostly compiled out) |
| `tools.func_id` CRT signatures | 11 (`_ftol`, `memmove`, `_alldiv`, `strcpy`, …) |
| `tools.rtti` | 0 (RTTI compiled out) |

**Unnamed: 1,193** (mostly `.text`). These are expected to be thunks, adjustor
thunks, CRT/internal helpers, and XDK inline glue. The vtable scanner already
found 12,228 vtable methods; many unnamed entries are the thunks between them.

### Remaining naming work (iterate on the source map)

1. Resolve the 1,193 unnamed (recompiler `recomp_lookup` resolves them by address
   regardless; naming is for readability and crash stacks).
2. Demangle quality: our `demangled_to_c` is pragmatic, not full. For readable
   output, prefer the demangled signature in a secondary field and use
   `Class::method` names via a per-function comment (see 04).
3. Apply `GhostU.map`/`Star_d.pdb` as cross-checks for the library sections.

## 4. GPU / NV2A surface

- `xbox_nv2a` provides NV2A registers, pushbuffer parsing (`nv2a_pb_exec.c`),
  and a D3D11 backend (`nv2a_gpu_d3d11.cpp`, 144 KB).
- The game's D3D section will probe NV2A MMIO; the runtime traps those (VEH on
  Windows; the POSIX path differs — verify on Linux).
- `gap-analysis.md` says register-combiner (pixel) and vertex-microcode
  translation are complete, texture unswizzle complete, palettized/signed formats
  done. Cube/volume/YUV partial. This is the strongest part of the runtime.

## 5. What "missing" actually means for bring-up

| Missing thing | Impact | Plan |
|---|---|---|
| `FscSetCacheSize` | none | stub |
| BINK FMV | intro/cutscene video | decode `.bik` with ffmpeg/libbink; or skip cutscenes for first boot |
| WMADEC | some audio (WMA) | decoder; most Ghost audio is XACT `.xwb`/ADPCM, so lower priority |
| XNET/Xbox Live | multiplayer only | leave stubbed; single-player unaffected |
| APU DSP effects | audio fidelity | accept for now (xboxrecomp stub) |
| Linux OpenGL D3D8 path | **not used** | target Windows/D3D11 and run under Proton; Vulkan backend is follow-on work |
