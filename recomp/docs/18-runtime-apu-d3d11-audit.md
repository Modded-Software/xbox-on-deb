# 18 — Runtime / APU / D3D11 hardcore audit + fix plan

An independent, code-grounded audit (two Claude Opus 5.5 consults + a direct read
of this tree, 2026-10-09) of the pushbuffer → D3D11 backend, the pushbuffer
executor, and the APU, looking for *obvious misses* — unbatched state churn,
missing culling, per-draw O(n) work, redundant GPU↔CPU syncs, dead code, and
correctness holes the release build hides. It supersedes the "Remaining targets"
line at the end of [17-executor-roadmap.md](17-executor-roadmap.md) and records
the execution order that is being worked now.

## Where the time goes (measured)

`logs/latest-runtime.log`, gameplay window = change between the 2nd and 3rd
stats dumps: **10.01 s @ 34.5 FPS, 286,238 draws (~830/flip)**.

| Phase | Time / 10 s | Counter behind it |
|---|---:|---|
| vertex stream Map/copy (`streams`) | 1.62 s | 281,131 append + 5,107 discard `Map`s |
| texture bind (`textures`) | 1.45 s | 25.3 GiB `memcmp`; 641 re-uploads (0.307 GiB) |
| sync / readback | 1.15 s | 920 readbacks, 1.5 GiB copied; wait 0.783 s, publish 0.280 s |
| CPU vertex prep (`fetch_attr`) | ~2.0 s | 25.2 M unique vertices (inferred: draw 6.29 s − D3D 4.27 s) |
| submit | 0.45 s | |
| setup | 0.43 s | |
| shaders | 0.23 s | **already cached** — not a problem |

`[GPU] draw time: 6.292 s, 62.9% of interval`. **P1–P4 together ≈ 4.3 s of the
10 s window** and are the path to 40+ FPS.

## Performance findings (ranked, smallest-fix-first)

| # | Where | Waste | Measured | Smallest fix |
|---|---|---|---:|---|
| **P1** | `nv2a_gpu_d3d11.cpp:1636` `map_stream` (called `:2691`) | One `Map`/`Unmap` pair per draw per stream | 1.62 s | Map(DISCARD) once per frame, every draw appends, `Unmap` once before submit |
| **P2** | `nv2a_pb_exec.c:2567-2620` `gpu_append_primitive` | `color_attr()`/`texcoord_attr()` rescan 16 attributes **per vertex** (`:2594`, `:2603`); ~11 `fetch_attr`/vertex; program path clears the whole 420-byte struct (`:2581`) | ~2.0 s | Hoist attr base/bounds/type once per draw; clear only `gpu_attribute_mask` attributes |
| **P3** | `nv2a_gpu_d3d11.cpp:1858-1865` | Full `memcmp` of every bound texture's source bytes, once per frame | 25.3 GiB; 0.463 s hash + 1.449 s phase | Skip when the source pages weren't guest-written since last check (page dirty bit / write-watch) |
| **P4** | `nv2a_gpu_d3d11.cpp:1210-1256` readback, `:1823-1829` CPU fallback | Staging copy + `SwitchToThread` busy-wait + publish; alias path uses CPU fallback though a GPU→GPU branch exists | 920 readbacks; 225 CPU fallbacks vs **0** alias copies | Route aliases through the existing GPU→GPU `CopySubresourceRegion` branch (`:1802`) |
| **P5** | `xbox_memory_layout.c:3615` `contig_block_at` | Shared lock + linear scan over up to `CONTIG_MAX_BLOCKS`=16384 entries **incl. freed** (`:3452`). Called from every `dma_resolve` (`nv2a_pb_exec.c:192`) and twice per APU DMA page | `g_cba_calls`/`g_cba_iters` counted but **never printed** | Print the counters first; then a page→block table (16k pages × u16) updated on alloc/free |
| **P6** | `nv2a_pb_exec.c:3059` | `getenv("RECOMP_PB_EXEC_VERBOSE")` on every draw | 286 k `getenv` | Cache in a static, as the rest of the file does |
| **P7** | `nv2a_pb_exec.c:3042-3056`, `:236-238` | Per-draw `fetch_attr` min/max probe, two `clock()`, two `gpu_clock_seconds()`/`dma_resolve` | 286 k probes, 572 k `clock()` | Put probe + timers behind `DIAG` |
| **P8** | `nv2a_pb_scan.c:344` `note()` | Survey counter runs on every method word even when `RECOMP_PB_SCAN` off | O(1), small | Only call `note()` when scan is set |
| **P9** | `apu_dsp.c:674-676`, `apu_core.c:627-680` | Audio thread holds `d->lock` through VP+GP+EP; GP loop `do dsp_run(1000) while(!idle)` uncapped; guest `VOICE_LOCK`/MMIO block on it | Not measured (`engine_glitches=0`) | Measure lock wait first; cap cycles/frame |
| **P10** | dead code | `nv2a_vsh_interp.c` (401 lines) + `nv2a_combiner.c` (216) built (`kernel/CMakeLists.txt:28-29`) but **zero callers**; live combiner is `nv_cpu_*` in `nv2a_shader_cpu.h`. `apu_mixer_*`/`mixer_render` (`apu_core.c:919-1113`) also dead | 0 runtime | Delete after confirming 0 callers |

## Correctness findings (ranked)

| # | Where | Bug | Evidence | Smallest fix |
|---|---|---|---|---|
| **C1** | `apu_vp.c:1236-1252` vs `:143-164` | Voice never checked against `voice_locked`: a guest-locked voice (format/base/end/volume mid-update) is mixed from half-written state (the `-10497` DC). xemu waits for unlock. **Tried and reverted two ways:** "skip the locked voice" dropped a voiced window every 5.33 ms and spliced the mix — **633** raw steps >8000 (max 27605) + 204 clipped samples in one a-mash capture vs **0–4** before; the wait-for-unlock variant released `d->lock` and perturbed frame-thread timing (user heard periodic artifacts). | `is_voice_locked` used only in `fe_method` (`:201`, `:286`); pre/post captures | **Keep original + `apu_declick`** (verified: 60 s host-audio monitor, 0 gaps / 0 clicks). If revisited, block-wait like xemu without moving the frame clock |
| **C2** | `apu_regs.h:363` `EP_FRAME_US 5333`; `apu_xaudio2.c:149`; `apu_core.c:482` | Real period is 5333.33 µs → audio 62.5 ppm fast (+3 samples/s); on a full queue `xa2_submit_samples` returns 0 and the caller drops the window silently | Queue sits 4–5/16; full after ~940 s, then a dropped 5.3 ms window ~every 85 s | Track period in ns (16000000/3) or pace on `BuffersQueued` |
| **C3** | `apu_core.c:415-444` `apu_declick` | Smooths any jump > 8000 (~24% full scale), masking real transients (e.g. the documented `-10497` DC for 3 s) | Design review | **Retained** (C1 reverted): pre-declick captures still show splices up to ~19k in busy combat |
| **C4** | release build (`recomp/game/build.sh:31`), `assert()` gone | Guest-controlled bounds unchecked: `apu_dsp.c:413` underflow → huge memcpy; `:475` `% (end-base)` ÷0; `:292` SGE past table; `apu_vp.c:232` handle 0xFFFF → `ssl[256]`; `:206` `list-1` > 3 | Code | Replace asserts with clamps / early returns |
| **C5** | `apu_vp.c:770`, `:846` | 72-byte `adpcm_block`; ADPCM `memcpy` copies up to `36 × samples_per_block` (≤1152) bytes; `seg_spb` parsed (`:816`) but unused | Code | Clamp `block_size` to `sizeof adpcm_block` |
| **C6** | `nv2a_pb_scan.c:320-337` | JUMP/CALL targets masked to 256 MB and unvalidated; unknown header types (bits 29–31 = 3..7) run as increasing methods | Log `walk budget exhausted at 8FFFE7C0` (256 MB in) → ~2 M garbage words executed | Stop/resync on targets ≥ `XBOX_CONTIG_BASE+XBOX_CONTIG_SIZE` and on unknown header types |
| **C7** | `apu_core.c:151` | After 50 held-off frames the APU IRQ runs anyway, on a second host thread, against single-CPU guest code | Not counted | Never bypass, or count bypasses |
| **C8** | `nv2a_pb_exec.c:1025`, `:1046`, `:3872` | `_Exit(EXIT_FAILURE)` on unknown attr type / out-of-range extent / unsupported state program — one bad vertex kills the game | Code | Reject batch + count, like `nonfinite` |
| **C9** | `nv2a_pb_exec.c:2155-2166` `color_attr` | Slot-3-empty fallback can pick slot 4 (specular) as diffuse, then slot 4 is read again as specular | Code | Exclude slot 4 from the fallback |
| **C10** | `apu_vp.c:914` | When a request ends exactly at `cbo==ebo`, the last sample is skipped on loop/segment end (same as xemu) | Code | Low priority; `cbo > ebo` with a matching loop condition |
| **C11** | `nv2a_pb_scan.c:120-121` | Survey labels wrong: 0x033C labelled cull-enable but is alpha func; cull-enable is 0x0308 | Code | Cosmetic |

## Not found (ruled out)

- Shader, constant and texture-state caches are healthy: 147 k constant reuses
  vs 139 k uploads; shader hit rate > 99.99%.
- Waiting at sync points is already spread over a ring of 8 queries (0.08 s in
  9.5 k waits).
- **Culling is NOT missing.** `nv2a_gpu_d3d11.cpp:1683` is only the startup
  default; `make_rasterizer` (`:2159-2173`) applies per-draw cull mode + front
  face from NV2A state. (An earlier consult claimed otherwise; withdrawn.)
- `note_unhandled` never runs (0 unhandled methods).

## Execution order (current work)

1. **C1** — ✗ reverted. Skipping locked voices spliced the mix (633 steps); the
   wait variant perturbed frame timing. Original + `apu_declick` verified good
   by a 60 s host-audio monitor (`test_audio_monitor.py`).
2. **P1** — one stream `Map` per frame (done; gameplay median 26.0 FPS, a-mash PASS).
3. **P2** — hoist vertex-fetch derivation out of the per-vertex loop.
4. **P3 + P4** — page-dirty-gated texture compare; GPU→GPU alias copy.
5. **P5** — print `g_cba_*` and size the win before changing anything.
6. **P6/P7/P8/P10** — cheap cleanups + dead-code deletion.
7. **C2, C4, C5, C6, C8, C9** — correctness hardening after the perf tracks.

Per track: `bash recomp/game/build.sh`, then
`python3 recomp/tests/run.py --user-state --only a-mash` (plus `--only audible`
for C1). Hand-edits to generated code go in `recomp/game/MANUAL_PATCHES.md`;
status lands in `AGENTS.md`.

## Provenance

Two Claude Opus 5.5 consults, 2026-10-09 (`scripts/ask-claude.sh`, sessions
`ses_*` for pid 2404004 / 2415030), reading this tree plus
`logs/latest-runtime.log`. The author re-verified `map_stream`, the texture
`memcmp`, the readback busy-wait, `is_voice_locked` call sites, the dead
`nv2a_vsh_interp.c`/`nv2a_combiner.c`, and the `nv2a_pb_scan.c:320-337` masking
directly in the tree before recording them here.