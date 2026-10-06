# 09 — Performance: where the frame goes

The menu runs at ~12 FPS and the input feels seconds behind. This is the first
attempt to say where the time actually goes, from the runtime's own counters
rather than from intuition. It is a catalogue of the pipeline and a ranked list
of things to try, not a set of fixes yet.

## How this was measured

Much of the runtime is already instrumented, so no new code was needed:

- `[GPU-D3D11] time:` / `draw phases:` — phase timers in
  `src/kernel/nv2a_gpu_d3d11.cpp` (`gpu_timing`, reported by `nv2a_gpu_report`).
- `[GPU] presentation:` / `draw time:` / `[GPU] draws` — the executor's own
  counters in `src/kernel/nv2a_pb_exec.c` (`nv2a_pb_exec_report`, once every
  10 s).
- `[FETCH]` / `[READ]` / `[FILE]` / `[PATH]` — asset I/O from the kernel layer.
- `[KERNEL] ordinal` counts and the `xbox_log` throttle.

The numbers below are the report at the main menu (last 10 s interval of a ~60 s
run, ~1,000 flips). They are cumulative, so compare *deltas* between reports.

## 1. The machine: which threads exist

Guest threads (from `[KERNEL] PsCreateSystemThreadEx` in the boot log):

| # | Routine | Behaviour |
|---|---|---|
| 1 | `0x001B3E34` | first call, **run inline** on the host main thread — this *is* the game starting (`kernel_bridge.c:613`) |
| 2 | `0x001B3E34` | real spawned worker (`kernel_bridge.c:544`), context `0x00147280` |

So the "2 Xbox threads" are real and map to two host threads. Recompiled code
keeps its registers in thread-local storage (`RECOMP_TLS`) and each thread gets
its own simulated stack and TIB (`xbox_AllocThreadTib`), so they genuinely run
concurrently.

They synchronise through one guest critical section at `0x0031A818`, taken at
guest site `0x0030FCBA` (`[CS]` lines, 54 in a boot). Contention is *mild* —
this is not the bottleneck.

Host-side helper threads (all real Win32 threads):

| Thread | Created in | Job |
|---|---|---|
| main | — | guest thread 1; also the D3D11 executor |
| worker | `kernel_bridge.c:553` | guest thread 2 |
| ohci | `ohci.c:1148` | OHCI controller, 4 ms tick |
| kernel timer | `kernel_bridge.c:2637` | guest timers/DPCs |
| nv2a ack | `xbox_memory_layout.c:1064` | NV2A interrupt ack |
| watchdog | `xbox_memory_layout.c:1729` | hang reporting |
| fb window | `fb_present.c:589` | GDI window + blit |
| video pump | `video_pump.c:174` | overlay video |
| APU/waveOut | `apu_shim.h:80` | audio out |

**Conclusion:** the thread model is not broken. Two guest threads on two host
threads with their own TLS register files is the intended design, and the lock
between them is not hot. The frame time is spent inside the renderer, on the
guest threads, not in scheduler contention.

## 2. The frame pipeline, end to end

```
 guest (2 threads) builds NV2A pushbuffer in guest RAM, advances DMA_PUT
        │
        ▼
 nv2a_pb_exec.c        walk the method stream; rasterise screen-space batches;
        │              translate the rest to D3D11 draw calls
        ▼
 nv2a_gpu_d3d11.cpp    record draws into offscreen D3D11 render targets
        │
        ▼  NV097_FLIP_STALL  (nv2a_pb_exec.c:3554)
 nv2a_pb_exec_flush() → nv2a_gpu_flush() → nv2a_gpu_sync()
        │              readback EVERY dirty surface GPU → guest RAM
        │              (blocking D3D11_MAP_READ, waits for the GPU)
        ▼
 xbox_FramebufferWindowPresent (fb_present.c:62)
        │              CPU memcpy guest framebuffer → double buffer
        ▼
 fb_thread             StretchDIBits into a GDI window
        ▼
 DXVK → Vulkan → display
```

The important structural fact: **there is no D3D11 swapchain.** The GPU renders
offscreen, the result is read back into guest RAM every flip, and the visible
window is fed by a GDI blit of guest RAM. Every frame therefore pays a blocking
GPU→CPU round trip that a direct swapchain present would not.

## 3. The measured budget at the menu

From the last report (`recomp/game/recomp_boot.log:3869-3886`):

| Counter | Value | Share of a 10 s interval |
|---|---|---|
| `draw` (executor CPU) | 28.0 s cumulative | **~65 %** per interval |
| `draw phases: setup` | 8.13 s | per-batch CPU setup |
| `draw phases: textures` | 15.43 s | texture bind/validate/upload |
| `draw phases: shaders` | 2.31 s | shader variant lookup |
| `draw phases: streams` | 1.85 s | vertex stream append maps |
| `hash` (texture change detect) | **14.36 s, 61.95 GiB hashed** | the single biggest line |
| `sync` (readback/publish) | 14.67 s | |
| — `readback: wait` | **10.72 s** | blocking on the GPU |
| — `publication` | 3.74 s | CPU copy back to guest RAM |
| readbacks | **16,333 color + 11,923 depth** | |
| texture uploads | 81 created, ~1,000 updated, 0.05 GiB | almost nothing |
| vertex prep | 24.2 M attribute fetches, 61.7 M skipped | |
| streams | 5,975 discard + **270,979 append** maps | |
| unhandled methods | 31,304 (**50 distinct**) | |

Read it as: the CPU spends most of its frame time (a) re-hashing textures that
almost never change, and (b) blocking on GPU readbacks, while the rest goes to
per-batch setup for a very large number of small draw calls.

## 4. Root causes, ranked

### 4.1 Texture change detection by full `memcmp` on every bind — 14.4 s / 62 GiB

`nv2a_gpu_d3d11.cpp:1591-1601`. To decide whether a bound texture needs
re-uploading, the backend walks the texture cache and `std::memcmp`s the entire
source image in guest RAM against a stored snapshot. With hundreds of binds per
frame and multi-hundred-KiB textures this is 62 GiB of comparison per minute,
and only ~1,000 uploads actually result. Nearly all of it is waste.

### 4.2 Full readback + publish on every flip — sync 14.7 s, wait 10.7 s

`NV097_FLIP_STALL` calls `nv2a_pb_exec_flush()` (`nv2a_pb_exec.c:3555`) →
`nv2a_gpu_sync()` (`nv2a_gpu_d3d11.cpp:1071`), which read-backs **every dirty
color and depth surface**, `Map(..., D3D11_MAP_READ)` blocking until the GPU
has finished. 16k color + 12k depth readbacks over a minute, 10.7 s spent
waiting. Only the displayed surface strictly needs to be in guest RAM to be
blitted; the rest is speculative.

### 4.3 Per-batch CPU setup and vertex preparation — 8.1 s

~300 k hardware batches, ~74 M indices. For each batch the executor fetches and
transforms attributes (`fetch_attr`), zeroes buffers (9 GiB avoided by a skip
path that still runs 24 M fetches), and rebuilds stream state. This is
proportional to the draw-call count, which is high because the title emits many
small batches.

### 4.4 The CRT fatal path fires 44,000 times a boot

`getptd` (`0x002A6BD1`) branches on the byte at `fs:[0x24]`; when it is ≥ 2 it
`push 0xA; call [0x3618F0]`, and `0x3618F0` is the **KeBugCheck kernel thunk**.
Our `bridge_KeBugCheck` logs and returns (`kernel_bridge.c:1689`), so execution
continues and the call repeats. On hardware this would halt, so our `fs:[0x24]`
is wrong — a correctness bug, and 44 k log writes were a measurable cost before
they were throttled. This may also mean CRT per-thread state is not what the
title expects, which is worth understanding before trusting any libc-dependent
timing.

### 4.5 50 distinct unhandled NV2A methods

31 k method submissions fall through to the unhandled counter. Each may force a
state fallback or a redundant path; the distinct list is in the report. Worth
mining as its own catalogue.

## 5. Quick wins (low risk, keep behaviour)

1. **Validate each texture at most once per frame.** Cache the memcmp result
   against a frame serial, so N binds of the same texture cost one comparison.
   Expected to remove most of the 14.4 s. Contained to one function.
2. **Coalesce / defer readbacks.** Publish the display surface at flip; defer
   other dirty surfaces until something actually consumes them (a CPU read or a
   texture-from-surface bind), and do all pending surfaces in a single Map/wait
   instead of one wait each. Expected to remove most of the 10.7 s.
3. **Fix or silence the KeBugCheck loop.** Throttling is done; the real fix is
   to make `fs:[0x24]` hold what the CRT expects (TIB field), or to identify the
   write that raises it.
4. **Reduce draw-call count** where the executor already recognises quads/arrays
   (batch merge) to cut setup; or keep a persistent index buffer instead of
   270 k append maps.
5. **Present the display surface through a D3D11 swapchain** instead of
   readback + GDI. Bigger change, removes an entire round trip and the fb blit,
   but must preserve guest-readable render targets.

## 6. Parallelisation opportunities

The executor is single-threaded on the guest thread, but its work is largely
embarrassingly parallel *within a frame*:

- **Vertex attribute fetch/transform** (24 M/frame-min): split batches across a
  worker pool. Each worker needs only a stack + TIB
  (`xbox_worker_stack_alloc`, `xbox_AllocThreadTib`) — cheap and already used.
- **Texture decode + hashing**: decode is per-row/per-texel; the hash could run
  speculatively on a worker while the main thread proceeds.
- **Readback/publish memcpy**: row-range split across threads; the Map/wait
  itself cannot be parallelised, which is why (5.2) matters more.
- **Keep the two guest threads as they are** — do not try to parallelise guest
  logic; the register model is per-thread but guest semantics assume exactly
  those two.

Caveat: any worker that touches recompiled code must allocate a guest stack and
TIB, and must not assume the main thread's `g_fs_base`. The D3D11 backend is
plain C++ and has no such constraint, so it is the safest place to start.

## 7. What not to do

- Do not remove readback wholesale: titles read render targets from CPU.
- Do not sample-hash textures without an escape hatch — a missed change is
  visual corruption. Gate behind an env var until proven.
- Do not parallelise the guest threads' own logic.

## 8. Next experiments (bounded)

1. Add per-surface readback counters and per-texture hash counters to size
   (5.1) and (5.2) precisely.
2. Implement (5.1) behind `RECOMP_TEX_VALIDATE_ONCE=1`; re-measure `hash`.
3. Implement (5.2) behind `RECOMP_PUBLISH_LAZY=1`; re-measure `sync`/`wait`.
4. Re-examine `fs:[0x24]` for the KeBugCheck path.

## 8b. Catalogue: the unhandled NV2A methods at the menu

Ranked by submissions in the last interval (`[GPU]   0x....` lines). Most are
benign render state the executor does not need to act on; none should force a
fallback. Names from `src/nv2a/nv2a_regs.h`.

| Method | Count | Name / note |
|---|---|---|
| `0x1E98` | 4436 | `NV097_SET_TRANSFORM_PROGRAM_CXT_WRITE_EN` |
| `0x1D7C` | 1630 | `NV097_SET_ANTI_ALIASING_CONTROL` |
| `0x0318` | 1593 | `NV097_SET_POINT_PARAMS_ENABLE` |
| `0x031C` | 1593 | `NV097_SET_POINT_SMOOTH_ENABLE` |
| `0x0310` | 686 | `NV097_SET_DITHER_ENABLE` |
| `0x09F8` | 685 | unmapped (needs naming) |
| `0x147C` | 685 | unmapped (needs naming) |
| `0x1D9C` | 685 | `NV097_SET_CLEAR_RECT_VERTICAL` |
| `0x1D98` | 685 | `NV097_SET_CLEAR_RECT_HORIZONTAL` |
| `0x1D84` | 649 | unmapped (between AA control and clear value) |

Action: name the three unmapped methods and decide if any change pipeline
state. The rest can stay counted.

## 9. Results so far

Two changes committed to the toolkit, measured on the same menu scene:

| Change | Effect |
|---|---|
| Texture validation once per frame (`nv2a_gpu_d3d11.cpp`, `RECOMP_TEX_VALIDATE_ONCE`) | texture `hash` 14.4 s → ~2.1 s cumulative; FPS 12 → 16 |
| Guest ISRs entered at DISPATCH_LEVEL (`ohci.c`, mirror into `fs:[0x24]`) | KeBugCheck 44,026 → 25 per boot; FPS 16 → 18 |
| Completion-only sync + dirty-surface texture sampling (`RECOMP_SYNC_LIGHT`, now default on) | menu FPS 18 → **~30–35**; `sync` dominates no longer |

The ISR fix is the chapter-4.4 root cause: the OHCI driver's transfer-queue
routine lowers IRQL back to the level it was entered at, but we entered its ISR
at IRQL 0, so the lower-to-2 looked like a stuck raise and the guest TIB byte
`fs:[0x24]` stayed ≥ DISPATCH. `getptd` reads that byte and took its
`KeBugCheck(0xA)` path 44k times. A handful of device IRQLs (3, 4, 5) are still
not modelled, so ~25 mismatches remain; the dominant path is fixed.

Completion-only sync (`RECOMP_SYNC_LIGHT`) first **stalled** the title at the
video→menu transition, because `refresh_surface` re-uploaded a dirty surface
from guest RAM and overwrote the GPU's newer render with the previous publish.
The fix is in the texture path: while a surface is dirty it is sampled from the
GPU texture directly and `refresh_surface` is skipped. With that, ordering
events need no readback, and the menu holds ~30–35 FPS (stable over 130 s, no
crashes). `RECOMP_SYNC_LIGHT=0` restores the old full-publication behaviour.
The instrumentation that found this — `[GPU] flushes:` by reason — is kept.

## Evidence

- Boot log: `recomp/game/recomp_boot.log` — `[GPU]`, `[GPU-D3D11]`,
  `[KERNEL] PsCreateSystemThreadEx`, `[CS]`.
- Executor: `src/kernel/nv2a_pb_exec.c` (`nv2a_pb_exec_report`, flip handling).
- Backend: `src/kernel/nv2a_gpu_d3d11.cpp` (`nv2a_gpu_sync`, texture cache).
- Present: `src/video/fb_present.c` (`xbox_FramebufferWindowPresent`).
- Threads: `src/kernel/kernel_bridge.c`, `src/kernel/kernel_thread.c`.
