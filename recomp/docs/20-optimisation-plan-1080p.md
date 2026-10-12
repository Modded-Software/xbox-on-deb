WORKSPACE-VM workspace


> build · claude-opus-5-5

→ Read recomp/docs/15-performance-hotspots.md
→ Read recomp/docs/09-performance.md

$ ls -t recomp/diary/ ; ls -t logs | grep -m5 runtime ; git log --oneline -8 ; git -C refs/xboxrecomp log --oneline -8
resolution-1080p.md
nv2a-render-errors.md
perf-executor.md
kbm-bindings.md
runtime-20261011-004623.log
latest-runtime.log
runtime-20261011-004145.log
runtime-20261011-003841.log
runtime-20261011-003312.log
854fd56 launch: default render resolution to 1920x1080
3797fde video: progressive 1080p display-mode row + resolution diary
b724759 docs: diary R9 (fixup-block walk fix) and the executor perf notes
2a7fc97 docs: record the NV2A walk-loop fix (R8) and the KBM bindings
b2fc15a docs: move known-issues tracking out of AGENTS.md into the defects audit
4bd3e31 recomp: seed CXnIp timer; add NV2A diary, audit, framebuffer tools
136c1da input: session-keyed record/replay targets
7a6eca8 docs: make the user-path launch explicit; note walker bounds fix
cb0e8a9 nv2a: normalise tile-padded guest pitches to the linear stride
67608b8 nv2a-d3d11: log fixed-function skin_mode on reject (first 8)
f91c573 nv2a: cache hot getenv lookups; hoist per-primitive attribute layout
8913bfb nv2a: walker returns past the D3D8 fixup block (src+0x18)
f94853c input: KBM -- Y on right mouse, stick clicks, scroll aliases the left stick
33d1fe9 nv2a: return a reused push buffer to its caller (fix walk loop)
5f1f766 video: parse recorded key codes as hex; trace replayed keys
1308c40 nv2a: keep geometry on disabled textures; tolerate a bad SET_OBJECT; stop clobbering the fence

→ Read recomp/diary/resolution-1080p.md

$ cd logs && for f in runtime-20261011-004623.log runtime-20261011-004145.log; do echo "== $f"; grep -c . $f; grep -E "presentation:|\[KICK\]|GPU-D3D11\] (time|surface bytes|completion|readback|publication|sync)|flushes:|Levels.*nhc|DefaultWorld" $f > /tmp/opencode/perf_grep_$f.txt; wc -l /tmp/opencode/perf_grep_$f.txt; done
== runtime-20261011-004623.log
71764
65 /tmp/opencode/perf_grep_runtime-20261011-004623.log.txt
== runtime-20261011-004145.log
7349
9 /tmp/opencode/perf_grep_runtime-20261011-004145.log.txt

→ Read /tmp/opencode/perf_grep_runtime-20261011-004623.log.txt
✱ Grep "^(static |extern "C" |void |bool |int )[^;]*\b(nv2a_gpu_sync|gpu_sync_impl|nv2a_gpu_flip_publish|nv2a_gpu_flush|publish_surface|readback_surface|nv2a_gpu_wait|refresh_surface|publish_color|surface_publish)\w*\(" in refs/xboxrecomp/src/kernel · 8 matches
→ Read refs/xboxrecomp/src/kernel/nv2a_gpu_d3d11.cpp [offset=1180, limit=280]
→ Read refs/xboxrecomp/src/kernel/nv2a_gpu_d3d11.cpp [offset=900, limit=120]
✱ Grep "nv2a_gpu_(flip|sync|flush|surface_publish|wait)\(|nv2a_pb_exec_flush\(|xbox_FramebufferWindowPresent\(" in refs/xboxrecomp/src · 31 matches
→ Read refs/xboxrecomp/src/kernel/nv2a_pb_exec.c [offset=4195, limit=50]
→ Read refs/xboxrecomp/src/kernel/nv2a_pb_exec.c [offset=40, limit=40]
→ Read refs/xboxrecomp/src/video/fb_present.c [offset=55, limit=80]
✱ Grep "GSSetShader|geometry_shader|CreateGeometryShader" in refs/xboxrecomp/src/kernel · 10 matches
✱ Grep "gs_main|struct GSOut|nointerpolation|SV_PrimitiveID" in refs/xboxrecomp/src/kernel · 3 matches
→ Read refs/xboxrecomp/src/kernel/nv2a_gpu_shader.h [offset=60, limit=200]
✱ Grep "TIMESTAMP|RECOMP_SYNC_LAG|lazy_flip\(void|RECOMP_LAZY" in refs/xboxrecomp/src/kernel · 11 matches
✱ Grep "StretchDIBits|SetDIBitsToDevice|Present\(|BitBlt" in refs/xboxrecomp/src/video/fb_present.c · 5 matches
→ Read refs/xboxrecomp/src/kernel/nv2a_gpu_d3d11.cpp [offset=200, limit=90]
→ Read refs/xboxrecomp/src/kernel/nv2a_pb_exec.c [offset=78, limit=20]
✱ Grep "flip publication|sampling|GPU sample" in logs/runtime-20261011-004623.log · 0 matches
✱ Grep "gpu_sampling_enabled\(\)\s*$|static bool gpu_sampling_enabled|RECOMP_GPU_SAMPL" in refs/xboxrecomp/src/kernel/nv2a_gpu_d3d11.cpp · 1 match
→ Read refs/xboxrecomp/src/kernel/nv2a_gpu_d3d11.cpp [offset=190, limit=10]

$ grep -n "lazy_flip\|nv2a_gpu_flip\|LAZY_FLIP" -r refs/xboxrecomp/src recomp/game/src/main.c scripts/config.env > /tmp/opencode/lazy.txt; git -C refs/xboxrecomp log --oneline -S "lazy_flip" -- src/kernel/nv2a_pb_exec.c > /tmp/opencode/lazy_log.txt; cat /tmp/opencode/lazy.txt /tmp/opencode/lazy_log.txt
refs/xboxrecomp/src/kernel/nv2a_gpu.h:16:void nv2a_gpu_flip(const void *presented, size_t bytes);
refs/xboxrecomp/src/kernel/nv2a_pb_exec.c:80: * dirty one. Set RECOMP_LAZY_FLIP=0 to restore the full publish per flip (A/B). */
refs/xboxrecomp/src/kernel/nv2a_pb_exec.c:81:static int lazy_flip(void)
refs/xboxrecomp/src/kernel/nv2a_pb_exec.c:85:        const char *value = getenv("RECOMP_LAZY_FLIP");
refs/xboxrecomp/src/kernel/nv2a_pb_exec.c:87:        fprintf(stderr, "[GPU] flip publication: %s (RECOMP_LAZY_FLIP=%s)\n",
refs/xboxrecomp/src/kernel/nv2a_pb_exec.c:4213:         * Only that surface is published (nv2a_gpu_flip): a flip needs the
refs/xboxrecomp/src/kernel/nv2a_pb_exec.c:4222:                if (lazy_flip()) {
refs/xboxrecomp/src/kernel/nv2a_pb_exec.c:4225:                    nv2a_gpu_flip(base, (size_t)s_gpu.pitch * (h ? h : 1u));
refs/xboxrecomp/src/kernel/nv2a_gpu_d3d11.cpp:1449:extern "C" void nv2a_gpu_flip(const void *presented, size_t bytes)
0d82682 nv2a: lazy flip publication + targeted alias publish

$ git -C refs/xboxrecomp show --stat 0d82682 > /tmp/opencode/lazy_show.txt; git -C refs/xboxrecomp log --oneline -25 >> /tmp/opencode/lazy_show.txt; grep -l "flip publication" logs/*.log recomp/game/*.log > /tmp/opencode/lazy_logs.txt
(no output)

→ Read /tmp/opencode/lazy_show.txt
✱ Grep "^static void present_pvideo_overlay|xbox_FramebufferOverlay|memcpy\(dst" in refs/xboxrecomp/src/kernel/nv2a_pb_exec.c · 5 matches
→ Read refs/xboxrecomp/src/kernel/nv2a_pb_exec.c [offset=1836, limit=40]
I read both docs, the 1080p diary, the flip, sync and present code, and the latest 1080p runtime log. I didn't launch the game and didn't edit anything, so there's no diary entry for this.

## What the 1080p numbers show

The only 1080p log available, `logs/runtime-20261011-004623.log`, is **menu only**. It loads `menu.nhc` and never reaches the mission. Between reports 5 and 6 (364 flips at 36.4 FPS, so a 27.5 ms frame), each flip costs:

| Per flip | ms | What scales with pixels |
|---|---:|---|
| `sync` total | 5.6 | yes |
| `readback: wait` | 3.9 | yes, plus a full GPU drain |
| `publication: color` | 1.45 | yes |
| colour copied | 8.6 MB | one 1920×1080 surface (8.3 MB) |
| `hash` (texture memcmp) | 2.4 ms, **111 MB** | possibly (see step 4) |
| `xbox_FramebufferWindowPresent` memcpy | not timed | yes (8.3 MB) |

**The docs are partly out of date.** `15-performance-hotspots.md` says lazy flip publication was reverted. Runtime commit `0d82682` made it the default instead (`lazy_flip()`, `nv2a_pb_exec.c:81`). The flip now publishes **only the presented surface**: `nv2a_gpu_flip`, `nv2a_gpu_d3d11.cpp:1449`.

So the per-frame cost that 1080p makes 2.25× bigger is that one presented surface. All of it runs on the bottlenecked ack thread:

1. `CopySubresourceRegion` followed by a blocking `Map(READ)` in `gpu_sync_impl` (`:1295`). This drains the GPU completely every frame, so the CPU and GPU never overlap across the frame boundary.
2. Two 8.3 MB copies: into `source_snapshot`, then into guest RAM (`:1315`, `:1320`).
3. One more 8.3 MB copy in `xbox_FramebufferWindowPresent` (`fb_present.c:88`).
4. `refresh_surface` compares the whole 8.3 MB against the snapshot the next time that buffer is bound (`:929`).
5. On the fb thread, `StretchDIBits` of 1920×1080 through Wine GDI (`fb_present.c:966`). This competes for the roughly 2 usable cores.

This is the same kind of cost as the one lever that has worked before (GPU-sync wall time). Per-frame cuts at the flip have also paid off before (lazy flip gave +2 FPS, bulk unswizzle +14%); per-kick cuts were the ones the guest absorbed.

## Plan, in order

### Step 0 — Get a gameplay baseline (this decides the branch)
- Run `RECOMP_KICK_STATS=1 RECOMP_NV2A_GPU_TIMING=1 python3 recomp/tests/run.py --user-state --only performance` three times each with `RESOLUTION=1920x1080` and `1280x720`, on the same build. Take the median, and compute per-flip deltas of `sync`, `readback: wait`, `publication`, `hash`/`hashed GiB`, `ack cpu` and `walk avg`.
- Add one per-frame GPU timestamp pair (Begin/End around flip N to flip N+1, read back a couple of frames late) next to `collect_gpu_sample` (`nv2a_gpu_d3d11.cpp:210`). Report it as something like `[GPU-D3D11] gpu frame: X ms`. The existing sampler only times 1 draw in 128, so it can't tell you whether the GPU itself is the limit.
- **Decision:** if GPU frame time is 20 ms or more at 1080p, the GPU is the limit and you go straight to step 5. Otherwise continue with steps 1 to 4. The difference between 720p and 1080p is the size of the prize for steps 1 to 3.

### Step 1 — Pipelined (async) readback of the presented surface — highest leverage
- In `nv2a_gpu_flip`, stop calling `gpu_sync_impl(true, presented)`. Instead, copy the texture into a 2-slot staging ring (a new `Surface::pending[2]`, holding the staging texture, a copy of `written_region`, and a draw serial), `End()` an event query, and return without mapping.
- At the next flip, map the previous slot. Its event is already signalled, so there's no wait. Then do the publish half of `gpu_sync_impl` (`:1291–1342`), then `present_pvideo_overlay`, then `xbox_FramebufferWindowPresent`, all for **that** buffer. Those calls currently sit at `nv2a_pb_exec.c:4229–4231`, and the order matters: PVIDEO writes the YUV overlay straight into guest RAM (`:1874`), so a late publish would otherwise overwrite it.
- **Correctness rules:**
  - The surface stays `dirty` until its pending publish lands. That keeps the guard at `refresh_surface:925` working, which is what prevents the "stale RAM uploaded over the GPU image" corruption.
  - Mark it clean only if nothing was drawn into it after the copy (compare draw serials).
  - Any pending slot that overlaps the requested range must be resolved first in `nv2a_gpu_surface_publish` (blit source at `pb_exec.c:947`, alias at `d3d11.cpp:1908`) and in the full `gpu_sync_impl(true)`.
  - Drop the pending slot when a surface is evicted or recreated.
- Put it behind an A/B switch (for example `RECOMP_ASYNC_FLIP=0` to turn it off).
- **Proof:** `readback: wait` per flip goes to about 0. Median FPS of 3 runs at 1080p in gameplay improves. `a-mash` still reaches the mission. The `blit`/loading-screen CopyRects and FMV look correct, which the user has to confirm. Diary error counts stay at 0.
- **Risks:**
  - One extra frame of display latency (about 25–40 ms of input lag).
  - If the guest CPU reads the front buffer between flips (screenshots or save thumbnails through `LockRect`), it sees frame N-2. That can't be detected without memory tracking.
  - F12 / framebuffer-hash tests see a frame one step older. That's harmless, but expect the hashes to shift.

### Step 2 — Present straight from the GPU
- Create a DXGI flip-model swapchain on the fb window's HWND, using the existing device. On the ack thread at flip time, `CopyResource(surface.texture → backbuffer)` and then `Present(0,0)`.
- Keep the GDI path whenever the PVIDEO overlay is active, for Bink (`video_pump.c`), and as an env fallback.
- This removes the `fb_present` memcpy and the `StretchDIBits` work, and gives back the frame of latency step 1 added. Guest-RAM publication stays async from step 1, only so the guest and the tests can read it.
- **Proof:** `perf` via `scripts/21-profile-recomp.sh` shows the `fb_present.c`/`StretchDIBits` share dropping (it was 5.4% at 720p and should be larger at 1080p), and FPS is up.
- **Risks:**
  - DXVK's `Present` from a thread that doesn't pump the window's messages. Never block the fb thread on the ack thread, or the two can deadlock.
  - Resize and fullscreen handling.
  - The user has to verify every screen visually.

### Step 3 — Remove the leftover full-frame passes over the presented surface
- For a surface whose first operation each frame is a full clear (`clear_value_valid` / `get_surface(preserve=false)`), skip the `source_snapshot` copy (`prepare_surface_snapshot`) and the `refresh_surface` compare. Once the CPU no longer reads the surface back, that's one or two 8.3 MB passes saved per frame.
- **Proof:** `publication: color` per flip roughly halves, and `color_refresh_*` counters show no new refreshes.
- **Risk:** if the guest really does write into the front buffer with the CPU, the write is missed. Check `color_refreshed` before and after to see whether that ever happens.

### Step 4 — Texture `hash` traffic (111 MB per flip at the menu)
- Log the top sources by bytes hashed. If they are render-target aliases (for example the 1920×1080 `0x1E` linear framebuffer-as-texture seen in R4), validate them by surface serial or dirty state instead of `memcmp`: that's the `RECOMP_TEX_VALIDATE_ONCE` path in `get_texture`.
- **Proof:** `hashed GiB` per flip drops and `hash` time drops, with no visual change.
- **Risk:** missing a CPU-side change to the texture, which shows up as stale textures.

### Step 5 — Only if step 0 says the GPU is the limit
- The geometry shader (`gs_main`, `nv2a_gpu_shader.h:239`) runs on almost every draw (`d3d11.cpp:2866`). The GPU is an Arc A770, where geometry shaders are expensive. It's only needed for `depthSlope` (polygon offset) and for rejecting triangles with non-finite vertices. Bind `nullptr` when `depthOffset` is off and handle the non-finite case in the vertex shader.
- Note that geometry-shader cost scales with triangle count, not resolution. The per-pixel lever is the ubershader branching (fog and lighting modes), which would need specialised pixel-shader variants.
- **Proof:** the per-frame GPU timestamp and the `GPU sample ... GS=` invocation count both fall.
- **Risk:** z-fighting or decals breaking, and stray triangles from non-finite vertices.

### Step 6 — Render-thread split (the existing 35 FPS estimate)
Do this only after steps 1–3, because otherwise the split would mostly move the same 1080p readback work onto another thread.

## Realistic expectation
At the menu, steps 1–3 remove about 5–8 ms from a 27.5 ms frame, which could plausibly reach about 45 FPS there. Gameplay at 20–30 FPS is a 33–50 ms frame, so 45 FPS needs a cut of about 11–28 ms. I don't think the readback work alone covers that; the render-thread split will probably also be needed. Step 0's gameplay numbers between 720p and 1080p will show how much of the gap is the 1080p cost itself. All of this is runtime-only (`refs/xboxrecomp`); nothing in `recomp/game/src/recomp/gen/*` needs to change.
