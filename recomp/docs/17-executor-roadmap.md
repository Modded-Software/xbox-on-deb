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

- **40 FPS is reachable, but no single change gets there.** Two combinations
  should: *correct lazy publication + GPU vertex pulling* (~40–45), or *correct
  lazy publication + per-draw trimming* (~35–42).
- **60 FPS is not realistic yet.** It needs every phase below, a GPU frame under
  16.7 ms (measured 15–21 ms today), *and* the title not being vblank-capped at
  30 (unverified — Phase 0's hard gate).
- **Not worth doing:** splitting work across the two GPUs; a worker pool for
  vertex prep (fork/join over ~1,250 small draws costs more than it saves —
  Phase 2 deletes that work instead).

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

### Phase 2 — GPU vertex pulling (the strongest pure-CPU cut)

Expected **−12 to −14 ms/flip**, ~+30–40% alone; risk medium-high.

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

The gameplay window (lazy) is still `draw`-dominated: ~1,180 draws/flip, draw
~55% of wall, `texture` + `streams` phases the largest sub-costs. Phase 1 did
**not** make the texture round-trip the gameplay bottleneck (it removed it
cleanly — `refresh_surface` full-uploads stopped at 69 total and the ~200/flip
full syncs are gone), but the per-draw cost is. That keeps **Phase 2 (GPU vertex
pulling)** as the strongest next cut, with **Phase 3 (per-draw trimming:
vertex constants out of `Constants`, per-stage texture-bind fast path)** behind
it. Re-run the A/B with `RECOMP_LAZY_FLIP=0` after Phase 2 to attribute gains.

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