# 17 — Executor roadmap: a plan to 40–50 FPS (and what 60 needs)

This is the plan of record for lifting in-mission frame rate from the current
~16–20 FPS toward 40–50, and it records exactly what each step buys and risks.
It supersedes the ranked lists in [15-performance-hotspots.md](15-performance-hotspots.md)
and [16-present-path-audit.md](16-present-path-audit.md) where they conflict,
because it is grounded in a fresh independent read of the hot code (a Claude
Opus 5.5 consult, 2026-10-09) plus this repository's own counters. The system
description is [10-architecture.md](10-architecture.md); the earlier budgets are
[09-performance.md](09-performance.md) and [15-performance-hotspots.md](15-performance-hotspots.md).

## Bottom line

- **40 FPS is reachable, but no single change gets there.** Correct lazy
  publication is in (+10%). GPU vertex pulling was tried and **rejected**
  (3–4% slower — it only covers 16% of draws and moves the copy into the
  backend). The first real win was **bulk-unswizzling the 0x06/0x07 texture
  decode**: 21.9 → 24.9 FPS (+14%). See "Phase 2 results".
- **60 FPS is not realistic yet.** It needs every phase below, a GPU frame under
  16.7 ms (measured 15–21 ms today), *and* the title not being vblank-capped at
  30 (**Phase 0 settled this: it is not capped**).
- **Not worth doing:** splitting work across the two GPUs; GPU vertex pulling
  (measured slower, not faster); a worker pool for vertex prep (fork/join over
  ~1,250 small draws costs more than it saves).

## Where a frame goes (per flip)

From the last 10 s window of `logs/runtime-20261009-164402.log`
(193 flips, 19.3 FPS, ~1,256 draws/flip). Per-flip milliseconds:

| Bucket | ms/flip |
|---|---:|
| prep (`gpu_raster_batch`: `fetch_attr`, de-index, state struct) | 9.0 |
| draw: setup | 2.8 |
| draw: textures (`texture` 11.1; upload 5.4, hash 1.8) | 11.9 |
| draw: streams (126k unique vertices/flip, 7.6 MB memset) | 7.3 |
| draw: shaders (~1.9 of it compiles) / submit | 2.7 / 1.9 |
| sync (readback wait 4.1, publish 2.0) | 6.4 |
| **not measured** (walk, method decode, flip) | **~9.5** |

Three readings of this table drive the plan:

1. **~21 µs per draw is 4–5× what a lean D3D11 translation layer costs under
   DXVK.** The waste is in our code, not the driver.
2. **The texture upload is a per-texel decode.** ~2.7 textures/flip, ~1 MB, in
   5.4 ms (≈190 MB/s) through the function-pointer swizzle decode in
   `get_texture` (`nv2a_gpu_d3d11.cpp:1898`). These are almost certainly colour
   surfaces published to RAM at flip and then re-decoded/re-uploaded every
   frame — a round trip that need not exist.
3. **The "guest refills freed executor capacity" conclusion is unfounded.** "0.95
   wall-s/s busy" is true of any bottleneck and proves nothing; `ack cpu` also
   counts the `SwitchToThread` spin loops (`xbox_memory_layout.c:1163,1246`) as
   CPU time. A fixed scene cannot emit more draws/frame because the executor got
   faster. Future A/B runs must record **draws/flip and method-words/flip**
   alongside FPS; if those stay flat while kicks/flip rises, a fixed cost is paid
   per kick and that is the thing to find.

## Correctness first: why the reverted lazy-publication attempt corrupted

The ~39 FPS "publish only the presented surface" experiment was reverted for
corruption. Reading the code, the corruption is most likely **self-inflicted by
the runtime**, not caused by the guest reading an unpublished target:

- `nv2a_gpu_flush()` (`nv2a_gpu_d3d11.cpp:1401`) calls full `nv2a_gpu_sync()`
  (publishes every dirty surface to RAM) and then marks **every** surface
  `needs_refresh = true` (`:1404`).
- `get_surface()` (`:978`) calls `refresh_surface()` for a matched surface.
  `refresh_surface()` (`:893`) only does the row-diff memcmp path when
  `snapshot_valid && !dirty`; otherwise it falls through to
  `UpdateSubresource(surface.texture, …, surface.memory, …)` (`:928`) — i.e. it
  **uploads whatever is in guest RAM over the GPU texture**. If the surface is
  dirty and unpublished, RAM is stale, so this overwrites newer GPU content.

So the invariants for a safe lazy publication are:

- **(a)** Never refresh a *dirty* surface from RAM.
- **(b)** At flip, still bump `s_texture_validate_serial` (only `gpu_sync_impl`
  does, `:1375`), and mark only *clean* surfaces `needs_refresh`.
- **(c)** Publish only the presented surface at `NV097_FLIP_STALL`.
- **(d)** Every runtime reader of guest RAM (texture memcmp, `refresh_surface`,
  blit, `fb_present`, F12 capture) must publish its range first; the blit path
  already uses `nv2a_gpu_surface_publish` (`nv2a_pb_exec.c:894`).
- **(e)** Only then add a `PAGE_NOACCESS` + `watch_veh` diagnostic (all mirror
  views) to learn whether the *guest* ever reads an unpublished target. If it
  does not during a mission, ship without VEH.

Treat the 39 FPS glimpse as an upper bound: a frame with missing geometry may
simply have drawn less.

## Ranked plan

### Phase 0 — Measurement (no risk; prerequisite)

- Report everything **per flip**, not per second.
- Time the currently unmeasured ~9.5 ms/flip (walk, method decode, flip).
- Split the texture phase: decode/upload vs hash vs `refresh_surface` memcmp vs
  alias scans.
- Subtract spin time from `ack cpu` (the `SwitchToThread` loops count as CPU).
- **Hard gate:** count vblanks between flips / read the guest present interval to
  determine whether the title is 30 FPS capped. If it is, 60 means patching guest
  timing (game logic may depend on frame rate), and the target must be re-scoped.

### Phase 1 — Correct lazy publication (most likely to break 40)

Expected **19 → 28–38 FPS**; risk medium (high only if VEH turns out necessary).
Implement the invariants (a)–(e) above. This also deletes the ~5.4 ms/flip
per-texel re-decode and ~5.7 full-surface memcmps/flip.

### Phase 2 — GPU vertex pulling (REJECTED after implementation; see results)

Expected **−12 to −14 ms/flip**, ~+30–40% alone; risk medium-high. Built and
measured; it came out **3–4% slower**, not faster. Root cause: vertex
preparation is only ~18% of the executor interval (backend draw is ~50%), the
pull path only covers the vertex-program branch (~16% of draws; the other 84%
are fixed-function), and the per-draw raw-span copy (2.29 GiB, avg 45 KB/draw)
moved work *into* the backend and cancelled the fetch saving. Ripped out; the
tree is back to the committed Phase 1 state. Details in "Phase 2 results".

- Bind the guest vertex byte range as a `ByteAddressBuffer`.
- Pass per-attribute offset/stride/type in a constant buffer.
- Decode F / S1 / S32K / UB_D3D / UB_OGL / CMP in the vertex shader by
  `SV_VertexID`.
- Pass guest indices straight through, rebasing with BaseVertex.

Deletes the per-vertex `fetch_attr` loop (`nv2a_pb_exec.c:2552`), the 148–272 B
float4 vertex staging and its memset, and the per-vertex texcoord NaN loop
(`nv2a_gpu_d3d11.cpp:2597`; the NaN fix moves into the shader). Keep the CPU path
for inline/immediate draws and as a fallback.

### Phase 3 — Trim per-draw overhead (low risk)

Expected **−6 to −10 ms/flip**.

- Move the ~3 KB of vertex constants out of `Constants`, which is rebuilt and
  memcmp'd every draw (`nv2a_gpu_d3d11.cpp:2459,2664`). Give them their own
  buffer, updated only when transform-constant methods bump a generation counter.
- Per-stage texture-bind fast path: if (source, key, serial, surface generation)
  is unchanged, skip the alias scans (`:1745–1760`).
- Replace the per-texel swizzle decode with a table-based bulk unswizzle.

Caching vertex-program/constant *words* at the method level is not worth it
(~42k words/flip costs under 1 ms).

### Phase 4 — Render thread owning the D3D11 context (after 1–3; high risk)

Splits ~8–10 ms of walk/index work from ~10–12 ms of backend; the GPU
(15–21 ms) then caps. DXVK already has its own command thread, so this only takes
*our* code off the critical path. The docs' old "~35" ceiling was
`max(stage A, stage B)` on stale numbers and ignored queue snapshot/copy cost.

### Phase 5 — Skip the geometry shader (needed for 60; no FPS today)

`gs_main` (`nv2a_gpu_shader.h:239`) only does NaN culling, polygon-offset slope
and the flat-shading provoking vertex. Bind it only when polygon offset or flat
shading is on; drop NaN primitives in the rasterizer; compute the slope with
ddx/ddy in the pixel shader.

### Explicitly rejected

| Idea | Verdict |
|---|---|
| D3D11/DXGI swapchain on its own | +0–10%; fold into Phase 1c, do not do separately |
| Worker pool for vertex prep | fork/join over ~1,250 small draws costs more than it saves |
| Draw merging / batching | ~half the draws change constants; +0–5% |
| Split work over the two GPUs | one immediate context can't be split; cross-adapter RT copies every frame; GPU isn't the bottleneck |

## Is 60 realistic?

- Phases 1–3 single-threaded: ~20–25 ms/frame → **40–50 FPS**.
- + Phase 4: CPU stage ~12 ms, GPU caps at 15–21 ms → **47–60 FPS**.
- 60 additionally needs Phase 5 and a title that is not vblank-capped.

## Phase 0/1 execution results (2026-10-09)

### Phase 0 — measurement: the 30 FPS cap is NOT present

Added a flip-interval histogram (`RECOMP_FLIP_PACING`, on by default;
`xbox_Nv2aFlipPacingReport` in `xbox_memory_layout.c`, called from the executor
report) and a one-line startup print of the publication mode. The buckets are
vblank-relative (`<16.7 / 16.7-24 / 24-34 / 34-50 / 50-67 / 67-100 / >100` ms)
because the runtime serves vblank at 60 Hz (`XBOX_FRAME_PERIOD_MS`).

Observed (run `runtime-20261009-181620.log`): the menu window hit **38.25 FPS**
with **94% of intervals in 24-34 ms** (mean ~26 ms), and gameplay sits at
**34-50 ms** (mean ~44 ms, executor-bound), not at 33.3 ms. A 30 FPS cap would
plateau at 33.3 ms; we passed it. **60 is worth pursuing.** (The histogram also
confirms the earlier 12-20 FPS numbers were executor slowness, not a title cap.)

### Phase 1 — correct lazy publication: neutral alone, +10% once the real blocker was removed

Implemented as planned: `refresh_surface` refuses to upload a dirty surface from
RAM (the stale-RAM corruption); `nv2a_gpu_flip` publishes only the presented
surface and marks only clean surfaces `needs_refresh`; `NV097_FLIP_STALL` calls
it for `drawn_offset` and falls back to the full flush otherwise. `RECOMP_LAZY_FLIP=0`
restores the old full publish per flip.

The lazy flip **alone measured flat** (gameplay median 20.0 vs 19.9 FPS) because
its saving was immediately undone elsewhere: `get_texture`'s non-copyable
dirty-alias branch called a full `nv2a_gpu_sync()` **once per frame** (the
`source aliases: CPU synchronization fallbacks` counter climbs ~1/flip), which
republished every surface the lazy flip would have skipped. Making that branch
**targeted** (`nv2a_gpu_surface_publish(binding.source, binding.source_bytes)`)
unmasked the saving:

| | gameplay median (25 s, n=24) | menu window |
|---|---:|---:|
| `RECOMP_LAZY_FLIP=0` (full) | **21.0 FPS** | ~29.9 FPS |
| `RECOMP_LAZY_FLIP=1` (lazy, default) | **23.0 FPS** | ~38.3 FPS |

Correctness with lazy on: `a-mash` PASS, `audible` PASS, and the mission run has
0 `rejected:`, 0 `DMA-AMBIG`, 0 `texture target alias`, 0 decode/compile/create
failures.

**Residual risk:** a non-presented surface that the *guest CPU* reads straight
from RAM after a flip would now be stale. It was not seen in the menu, briefing,
HUD or first mission. The planned `PAGE_NOACCESS` + VEH diagnostic to settle it
is still deferred; `RECOMP_LAZY_FLIP=0` is the escape hatch.

### What the numbers say about the remaining targets

The gameplay window (lazy) is still `draw`-dominated: ~1,240 draws/flip, draw
~66–70% of wall. Phase 1 did **not** make the texture round-trip the gameplay
bottleneck (it removed it cleanly — `refresh_surface` full-uploads stopped at 69
total and the ~200/flip full syncs are gone), but the per-draw cost is. The
draw-phase breakdown (per 10 s of gameplay, `runtime-20261009-204914.log`) is:

| draw sub-phase | s / 10 s |
|---|---:|
| textures | 2.64 |
| streams (vertex/index staging) | 1.52 |
| submit | 0.41 |
| setup | 0.36 |
| shaders | 0.08 |

Within `textures`: `upload` 1.67 (the per-texel decode), `hash` 0.37 (the
per-frame source memcmp), the rest alias scans/refresh. **GPU vertex pulling
(Phase 2) was the wrong first move**: it targets `streams`/prep while only
covering 16% of draws, and it was measured slower. The decode was the real wall.

### Phase 2 results — vertex pull rejected, swizzled-32bpp decode fixed instead

- **Vertex pull: 3–4% slower.** Measured same-scene (per 10 s): preparation
  `1.83 → 1.11 s` (the fetch saving, as designed) but backend `5.00 → 5.99 s`,
  net `+0.3 s`. Only `54,803 / 339,607` batches (16%) hit the pull branch; the
  raw span is ~45 KB/draw (9× the ~5 KB of referenced vertices), so the
  per-draw copy cost more than the fetches it removed. Fully reverted.
- **Swizzled 32bpp decode: gameplay 21.9 → 24.9 FPS (+14%).** Format `0x06`
  (swizzled A8R8G8B8, linear twin `0x12`) was **78% of all upload bytes**
  (~1 MB/upload, ~1/frame) and was decoded through a per-texel indirect
  callback. `xbox_unswizzle_rect` (already in `d3d8_swizzle.h`) bulk-unswizzles
  `0x06`/`0x07` by Morton order in `get_texture` (`nv2a_gpu_d3d11.cpp`). Texture
  phase halved (`2.64 → 1.36 s/10 s`), draw `70.3% → 65.9%` of wall. 0
  `rejected`, 0 decode failures; `a-mash` and `audible` PASS.

Remaining targets, in order: `streams` staging (1.5 s), `submit`+`setup`
per-draw D3D11 overhead (0.8 s), the texture `hash` memcmp (0.37 s), then
Phase 3 (vertex constants out of `Constants`, per-stage texture-bind fast
path) and Phase 4 (render thread).

### Known regression alongside this work: garbled / flangy sound

After the Phase 0/1 changes, many in-game sounds are reported flangy, stuttery
and garbled. It is an **audio-quality** fault, not liveness: `--only audible`
still PASSes (the captured APU PCM is non-silent). The GPU changes here do not
touch the APU, so the prime suspect is the mixdown — in particular the
`mcpx_apu_monitor_frame` overdub (`apu_core.c`) added by the earlier "audio
in-game" fix, since a doubled/delayed voice mix sounds exactly like flanging.
Bisect by ear against a pre-session build; `RECOMP_LAZY_FLIP=0` rules the GPU
publication path in or out. Open issue in `AGENTS.md`.

## Provenance

Claude Opus 5.5 consult, 2026-10-09 (`scripts/ask-claude.sh`), which read
`09`, `10`, `15`, `16` plus `nv2a_gpu_d3d11.cpp`, `nv2a_pb_exec.c`,
`nv2a_pb_scan.c`, `xbox_memory_layout.c` and
`logs/runtime-20261009-164402.log`. Its per-flip table and phase estimates are
reproduced above; the code invariants in "Correctness first" were re-verified in
this tree before being recorded as fact.