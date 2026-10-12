# 16 — Present-path audit: what Cxbx and xemu do that we do not

This is a point-in-time audit of the frame's structural cost, prompted by the
observation that Cxbx-Reloaded and xemu are generally faster. It records the
architecture gap, how the two references avoid it, a ranked list of real gaps,
and the approved remediation plan. The system description is
[10-architecture.md](10-architecture.md); the frame budget and earlier fixes are
[09-performance.md](09-performance.md); the running hotspot log is
[15-performance-hotspots.md](15-performance-hotspots.md). It is not a fresh
runtime session; numbers are from the logs cited in those documents unless a new
measurement is named.

## Bottom line

The obvious missing thing is the **present path**, and our own architecture
document already says so (`10-architecture.md:189`): there is no D3D11
swapchain. Every flip reads every dirty surface back from the GPU into guest
RAM, and a GDI window blits that to the screen. That round trip is the frame's
structural cost.

**Cxbx** presents through a D3D9 swapchain and never pays it. **xemu** renders
on a dedicated render thread, presents from the GPU, and downloads surfaces
**on demand** only when the guest actually reads VRAM. We do neither.

## 1. The gap

Per flip, our code does:

1. `NV097_FLIP_STALL` (`nv2a_pb_exec.c:4090`) → `nv2a_pb_exec_flush()`
   (`:44`) → `nv2a_gpu_flush()` → `nv2a_gpu_sync()` →
   `gpu_sync_impl(publish=true)` (`nv2a_gpu_d3d11.cpp:1188`), which
   `CopyResource` + `Map(D3D11_MAP_READ)`s **every dirty colour and depth
   surface** GPU→guest RAM, blocking the ack thread on the GPU.
2. `xbox_FramebufferWindowPresent()` (`fb_present.c:67`) memcpys guest RAM into
   a second buffer; `fb_thread` then `StretchDIBits` it through GDI
   (`fb_present.c:807`) → DXVK → display.

Measured: `sync` 1.2–2.7 s per 10 s, of which `readback wait ~1.9 s` is
*blocking on the GPU*; plus one or two full-frame CPU copies. The GPU is
otherwise idle-waiting because of the bounded ordering run-ahead.

## 2. How the references avoid it

### Cxbx-Reloaded (HLE)

Direct code execution plus HLE of D3D8 to D3D9, presenting through a D3D9
swapchain — no guest-RAM round trip at all. Relevant techniques:

- Dirty-flag tracking for fixed-function state; skip redundant computation and
  upload when the generation has not changed.
- A per-stage texture cache that skips redundant `SetTexture`/`GetHostBaseTexture`
  calls when the Xbox texture pointer and data address are unchanged (~6000
  calls/frame eliminated in one measured title).
- A vertex-buffer pool (power-of-2 buckets) instead of Create/Release per cache
  miss.
- **Render-target resources are special**: it skips CPU-hash-based re-creation
  because GPU content cannot be detected as "changed" by hashing guest memory.

### xemu (LLE — the same model as us)

Its Vulkan backend (`hw/xbox/nv2a/pgraph/vk/`) is the closest reference:

- A dedicated **render-command thread** with an SPSC queue (`render_thread.c`):
  the guest thread decodes and enqueues DRAWA/CLEAR/FLIP/FINISH/VERTEX_RAM/
  DOWNLOAD packets; the render thread owns the GPU context. A
  `RenderCommandSnapshot` copies the PGRAPH state so the render thread never
  reads live registers.
- **Draw merging** (`OPT_DRAW_MERGE_MAX`, up to 128 draws into one `vkCmdDraw`)
  plus a reorder window to minimise pipeline/state switches.
- **On-demand surface downloads**: `pgraph_vk_download_surfaces_in_range_if_dirty()`
  pulls a surface back only when the guest reads that VRAM range, and the
  display download is piggybacked onto the frame's own command buffer (no extra
  submit/fence). There is no per-flip readback of everything.
- Bindless textures (descriptor indexing), async shader compile, and
  compute-shader swizzle/unswizzle.

## 3. Ranked gaps

Estimates are not additive and assume the ack thread is the bottleneck. The
ranking merged two independent reads of our source (this session and a Claude
consult).

| # | Gap | Real for us? | Est. gain | Effort |
|---|---|---|---|---|
| 1 | **Present from the GPU (DXGI flip swapchain) + lazy on-demand downloads + drop ordering waits** | Yes — the core issue | +20–45% (19 → ~23–28) | Medium |
| 2 | **Write-tracked texture invalidation** instead of full `memcmp` every bind | Yes — the 2–3 s texture bucket | +15–30% | Medium |
| 3 | **GPU vertex fetch** — bind guest vertex memory, build the input layout from `SET_VERTEX_DATA_ARRAY_FORMAT`; move NaN-texcoord sanitising / NORMPACKED3 / w=0 into the vertex shader | Yes — the 1.3 s streams bucket, 404 B/vertex | +10–15% | High |
| 4 | **Render-thread split** (xemu's SPSC queue) | Yes, but only *after* 1–3, else it inherits the same waits | up to 1.5–2× if the guest thread has slack | High |
| 5 | Draw merging | Partly — `nv2a_pb_exec.c` already builds its own vertex/index lists, but we cannot merge across texture changes (no bindless on D3D11 FL11) | low single digits unless a counter shows ≥ ~30% of draws share a generation | Low–Med |
| 6 | Bindless textures | **No** — D3D11 Feature Level 11 has no descriptor indexing (needs D3D12/Vulkan) | n/a | — |
| 7 | Async shader compile / compute swizzle | Hitches only, not steady-state FPS | ~0 steady | — |

Why the references are faster, in one line each: Cxbx avoids the GPU-command-
stream cost via HLE and a swapchain; xemu has the same LLE cost we do but
overlaps it on a render thread, batches draws, and never reads a surface back
unless the guest asks.

## 4. Approved plan

### Phase 0 — ceiling probe (throwaway)

An env-gated build (`RECOMP_STALE_PRESENT=1`) that presents stale frames and
skips both the flip publish and the ordering waits. The resulting FPS is the
ceiling Phase 1 can reach, and confirms the ack thread is waiting rather than
CPU-bound (cross-check `[KICK]` walk% against `ack cpu%`; walk ~96% with low
CPU% means waiting).

### Phase 1 — GPU present + lazy downloads

1. `fb_present.c`: keep the window and its message pump; drop the GDI blit and
   create a DXGI flip-model swapchain (2–3 buffers) on the window using the
   **same device** as `nv2a_gpu_d3d11.cpp`. `Present` from the thread that owns
   the immediate context (D3D11 contexts are not thread-safe).
2. New `nv2a_gpu_present(addr, pitch, w, h)`: find the `Surface` whose
   `memory == addr`, draw it to the back buffer with a fullscreen-triangle
   shader (this also handles scaling), then `Present`. If no surface matches
   (Bink frames or the pvideo overlay written into RAM by the CPU), fall back to
   `UpdateSubresource` from guest RAM into a scratch texture.
3. `NV097_FLIP_STALL`: call `nv2a_gpu_present` instead of
   `nv2a_pb_exec_flush`; bump `s_texture_validate_serial` without publishing.
   Surfaces stay dirty and GPU-resident.
4. Remove the refresh-all step from the flip path (Cxbx's "render targets are
   special"): refresh a surface from RAM only on a known CPU write
   (`nv2a_gpu_surface_modified` from blits, or a write fault).
5. Drop the GPU waits from `semaphore_release` and `WAIT_FOR_IDLE`. The guest
   only observes memory, and command order is preserved by the immediate
   context; throttle with the swapchain's frame latency
   (`SetMaximumFrameLatency`) instead of `RECOMP_SYNC_LAG`. Exception: zpass /
   occlusion report writes (`report_zpass`) are real GPU→memory results and
   still need a query wait.
6. Download on demand only for things that read surface bytes from RAM: our own
   F12 capture and test framebuffer hashes (`xbox_FramebufferDumpBmp`) need an
   explicit readback; the guest CPU is unknown. The cheapest probe is to mark
   dirty surface pages `PAGE_NOACCESS` using the existing VEH infrastructure
   (`watch_veh`, `xbox_memory_layout.c:1719`) and log touches. Memory is a file
   mapping with mirror views, so all mirror views must be protected.

Expected effect: the `sync` bucket (1.2–2.7 s / 10 s) drops toward zero, the
per-frame surface memcmps go away, and CPU/GPU overlap returns.

### Later

- Phase 2: write-tracked texture invalidation (protect texture pages read-only,
  set `possibly_dirty` from the VEH write fault, memcmp only then; an
  N-frame re-validation is the cheaper fallback and risks up to N frames of
  staleness).
- Phase 3: GPU vertex fetch.
- Phase 4: render-thread split; draw merging only if Phase 0 instrumentation
  shows enough consecutive same-generation draws.

## 5. Smaller findings

- 2D blits currently do a GPU→RAM→GPU round trip (`image_blit_run`,
  `nv2a_gpu_d3d11.cpp:893/924`). When both ends are cached surfaces, use
  `CopySubresourceRegion`. Count blits first; xemu does these on the CPU.
- One shared ~4 KB constant buffer for all state is re-mapped on any change.
  Once the stream path is reworked, per-draw constants and vertices could share
  one per-frame ring using D3D11.1 `*SetConstantBuffers1` offsets, taking ~1500
  Maps/frame down to a few.

## 6. Caveat

The xemu details above are from its source, its PR history, and the project's
external documentation, not from running it. Check them against
`hw/xbox/nv2a/pgraph/vk/` before quoting them as authoritative in other docs.