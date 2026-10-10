# 12 - Runtime defects: mission load, audio, and the disassembly surface

This is a point-in-time audit of the two symptoms reported after the vertical-look
fix shipped, plus the disassembly-level surface that sits underneath them:

1. Some missions do not start, or crash shortly after they begin loading.
2. In-game sound is completely absent.

The static complexity audit is [11-audit.md](11-audit.md); the system design is
[10-architecture.md](10-architecture.md). This document records what the runtime
logs actually show, what the mechanism is, and the plan to fix it. Where a number
is quoted it comes from a named log file or source line, not from a fresh session.

Scope: the `recomp/` runtime direction. The emulator direction at the repository
root is out of scope.

## Method

Evidence is drawn from the runtime's own logs shipped in `logs/`:

| Log | What it captured |
|---|---|
| `logs/runtime-20261007-145412.log` | Mission load that exhausted the heap and crashed |
| `logs/runtime-20261007-131330.log` | An earlier crash in our own KBM code |
| `logs/runtime-20261006-172122.log` | A run where the APU demonstrably produced audio |

and from static reading of the runtime sources named inline. The mission crash is
deterministic and reproduced by loading `1_2_1_Miners_Bunker`.

## Symptom 1: mission load crash

### Evidence

The tail of `logs/runtime-20261007-145412.log`:

```
xbox_HeapAlloc: out of memory (requested 1841168, used 50765696/50855936)
  [HEAP] 1 live blocks of 8388608 bytes (8192 KB)
  [HEAP] ... (large live blocks totalling ~47 MB)
[ICALL] target 0x00000000 is not code -- skipped
[CRASH] Access violation at RIP=0x6FFFFCF517C0, fault addr=0x17746FF6C (read)
        in CreateFileA_28_001B2939+0x6E0
```

The crash is the second-order effect: a large allocation fails, the file-open path
that asked for it continues with a null/short buffer, and an indirect call through
`0x00000000` is skipped before the process dereferences a wild address. The guest
fault VA `0x17746FF6C` truncates to Xbox VA `0xFFFFFF6C`, a null-relative read.

### Mechanism

- The Xbox heap is carved from `XBOX_HEAP_BASE` (`0x00F80000`) to `XBOX_HEAP_TOP`,
  which is `g_xbox_map_size ? g_xbox_map_size : g_xbox_total_ram`
  (`xbox_memory_layout.h:444`). At the default 64 MB RAM that is a **48 MB heap**,
  matching the `used ... /50855936` in the log.
- The XBE is a **Debug build** (`recomp/build/xbe_parser.txt`: `Type Debug`,
  title "Starcraft: Ghost (Release)", debug path
  `c:\Star\CODE\GAME\xbox_Release\Ghost.exe`). Debug/beta XBEs ship for the
  **128 MB devkit** and size their allocations accordingly — the header comment at
  `xbox_memory_layout.h:43-48` records exactly this for Halo's cachebeta.
- `xbox_SetTotalRam()` and `XBOX_DEVKIT_RAM` (128 MB) exist
  (`xbox_memory_layout.h:48`, `:105`) but **nothing calls `xbox_SetTotalRam`**.
  The runtime reports retail 64 MB to the title
  (`XboxHardwareInfo` flags=0, `kernel_bridge.c:202-209`;
  `xbox_MmQueryStatistics` `TotalPhysicalPages` hardcoded to 16384,
  `kernel_memory.c:128`).
- The allocator (`xbox_HeapAlloc`, `xbox_memory_layout.c:3254`) is a bump allocator
  with a free-reuse path, but the reuse path is **first-fit without splitting**:

  ```c
  for (int i = 0; i < g_heap_block_count; i++) {
      if (!g_heap_blocks[i].free || g_heap_blocks[i].size < size) continue;
      if (g_heap_blocks[i].addr & (alignment - 1)) continue;
      g_heap_blocks[i].free = 0;        /* takes the WHOLE block */
      ...
  }
  ```

  It does not prefer the smallest sufficient block, and it never splits the
  remainder. A freed 8 MB block handed to a 276-byte request is marked used in
  full. The `[HEAP]` histogram printed at OOM groups live blocks by size and would
  report that 8 MB block as live even though only 276 bytes are in use. **The
  histogram therefore cannot be read as "47 MB genuinely needed"; it is an upper
  bound inflated by exactly this fragmentation.**

`xbox_HeapFree` (`xbox_memory_layout.c:3379`) does coalesce adjacent free blocks,
which limits but does not remove the damage: a large block reused for a small
object only becomes reusable again when that small object is freed.

### Conclusion

Two independent causes, either of which can produce the OOM:

- **A — the RAM model.** A devkit-targeted debug build is run against a retail
  64 MB model. If the title's own accounting uses `MmQueryStatistics`, it believes
  it has 64 MB and the 48 MB heap is simply too small for the mission's assets.
- **B — allocator fragmentation.** First-fit without splitting can strand large
  freed blocks on tiny live objects, exhausting the heap at a much lower true
  occupancy than reported.

Cause B is a real defect regardless of A, is fully in our control, and is the
cheaper of the two to eliminate with confidence.

## Symptom 2: missing in-game sound

### Evidence

The runtime is **not** silent internally. `logs/runtime-20261006-172122.log`
records a working voice pipeline:

```
[APU-START] id=69 fmt=A981E0E6
[APU-VOICE] id=69 source_peak=0.0720
[APU-ROUTE] id=69 bins=0-7 vol=183
[APU-DSP]   passthrough peak=0.12699
[APU-OUT]   nonzero=86362 hardware_nonzero=86362 peak=4161 voices=5
```

The VP decoded five voices and the mixdown emitted a non-zero peak that reached
the XAudio2 output. `/dev/snd` devices exist on the host (pcmC0..C4). So "no
sound" is not "the VP produced nothing" in that run.

### Mechanism

- The APU's GP/EP DSP is a **passthrough stub** (`apu_dsp.c`); the DSP handshake
  is faked with `RECOMP_APU_DSP_ACK=gp:0x810`, set by default in
  `recomp/game/src/main.c:236-237`. The real DSP programs (`nsidsp.bin`,
  `dsstdfx.bin`, both present in the game directory) are never executed.
- `xbox_DirectSoundCreate` (`audio/dsound_device.c:379`) is dead code — never
  called. The guest statically links DSOUND/XACTENG and drives APU MMIO directly.
- The runtime reports retail hardware (`XboxHardwareInfo` flags=0), which some
  titles use to select an audio tier.
- The observed diagnostic run may not have been in a mission (`[APU-START] id=69`
  is one voice set). Whether **in-mission positional/3D voices** program the VP
  the same way is unverified.

### Conclusion

Two candidate mechanisms, distinguishable by one diagnostic run:

- **C — the null mixdown/host route.** Voices are produced in-game but never
  reach the host sink (mixdown default, 3D/positional routing, or XAudio2
  endpoint). Fix is in the APU's output path.
- **D — the DSP program path.** The title relies on GP/EP DSP effects; the
  passthrough stubs drop them, and/or the fake `RECOMP_APU_DSP_ACK` handshake lets
  the title think DSP is ready when it is not. Fix requires running (or more
  faithfully faking) the DSP.

## Symptom 3: the disassembly surface

Not the cause of the crash above, but relevant to "fundamental issues with the
disasm":

- **Unimplemented instructions.** 238 decoded, of which the reachable sites are
  benign no-ops: `cli`/`sti` (`0x0035FDFD`/`0x0035FE0E`, an XPP spinlock),
  `in al,dx`/`out dx,al` (`0x002C972D`/`0x002CA640`, D3D PCI), and `wbinvd`
  (`0x002C7F44`, `0x00233188`). None sit on the mission-load or audio path
  observed so far.
- **Unresolved call stubs.** `recomp/build/gen_fresh/recomp_stubs_unresolved.c`
  declares **182** addresses called by translated code but not detected as
  functions. Each is an empty body that only consumes the pushed return address.
  A stub on a live path silently drops real work, which surfaces elsewhere as
  corrupted state. None are yet proven to be on the mission/audio path, but they
  are the highest-risk unknown in the translated surface.
- **The override layer is unbuilt** (already noted in [11-audit.md](11-audit.md)):
  `recomp_manual.c` is the empty template. This is the intended home for any
  per-title fix, and it is where a mission-load or audio fix would live.

## Plan

### Phase 0 — diagnostics (read-only runs)

1. Re-run with `RECOMP_APU_DIAG=1`, play through a mission, and record whether
   `[APU-OUT] nonzero` / `voices` stay non-zero in-game. This separates C from D.
2. Add an env-gated heap trace that logs, for allocations above a threshold, the
   **guest return address** from the guest stack and the size, so the live blocks
   can be attributed to call sites. This separates genuine need from fragmentation
   beyond what the split fix removes.

### Phase 1 — allocator (cause B, land first)

Make `xbox_HeapAlloc`'s reuse path **best-fit** and **split** the reused block so
only the requested bytes are consumed and the remainder stays free. This is
correct independent of the RAM question and is a small, contained diff. It
directly invalidates the inflated live-block histogram. Add a runnable self-check
that fails if a small request consumes a large freed block.

### Phase 2 — RAM model (cause A, behind a switch)

Expose RAM size as a runtime knob read before `xbox_MemoryLayoutInit`
(environment override, default unchanged at 64 MB), and — if and only if the
title proves to read it — make `xbox_MmQueryStatistics` derive its page count from
`g_xbox_total_ram` so the title's two signals agree. Boot at 128 MB and see
whether `1_2_1` loads. Default behaviour is unchanged, so a retail title is not
disturbed.

### Phase 3 — audio (C or D)

Whatever Phase 0 shows:

- If C: fix the APU output path (mixdown default / routing) so in-game voices
  reach the host sink.
- If D: escalate to the DSP program path, and re-evaluate whether the fake
  `RECOMP_APU_DSP_ACK` handshake should instead be a real (if minimal) GP.

### Phase 4 — translated surface (only if Phases 1–3 implicate it)

Sweep the 182 unresolved stubs against the mission and audio call graphs, seed
the real ones in `config/` and regenerate. Confirm the reached `[UNIMPL]` sites
stay benign.

## Resolution log

### 128 MB default and boot (done)

- `g_xbox_total_ram` now defaults to `XBOX_DEVKIT_RAM` (128 MB), with the
  `RECOMP_TOTAL_RAM_MB` environment override retained to go back to 64 MB.
  `xbox_MmQueryStatistics` reports pages from `g_xbox_total_ram` so the title's
  two memory signals agree.
- Boot initially failed at 128 MB: with the ~3.7 GB mirror span, letting the
  OS place the RAM mapping put it at offset `0x10000000`, so the tiled alias
  (guest `0xF0000000` + offset) landed on exactly `0x100000000` (4 GB), where
  `MapViewOfFileEx` fails with `ERROR_INVALID_ADDRESS`. Every rendering surface
  write then faulted in `memcpyFast` and boot stopped.
- Fix: base selection now tries candidate host bases and keeps the first whose
  tiled alias is actually mappable (`xbox_TiledAliasMappable`), skipping the
  known-bad 4 GB address. If the mirror span cannot be reserved at a candidate,
  the base is mapped alone and the mirrors are best-effort. At 128 MB this
  lands the base at `0x18000000`, the tiled aperture maps (`Tiled aperture alias
  verified`), and the title boots and renders.
- Baseline at 64 MB for contrast: the OS placed the mapping at offset
  `0x77470000`, whose tiled alias is `0x167470000`, so it never hit 4 GB and the
  old code worked by luck.

### Heap allocator (done)

- `xbox_HeapAlloc`'s reuse path is now best-fit and splits the reused block,
  instead of first-fit consuming the whole block. This removes the internal
  fragmentation that made the OOM histogram read high.
- `xbox_HeapSelfTest()` (`RECOMP_HEAP_SELFTEST=1`) verifies a small request
  reusing a freed large block reports the small size and leaves the remainder
  allocatable. It passes.

### Still open

- Mission load at 128 MB is unverified end-to-end; the next run should load
  `1_2_1` and confirm the OOM is gone with the larger heap and the split fix.
- In-game audio (causes C/D above) is not yet diagnosed.

## References

- [10-architecture.md](10-architecture.md), [11-audit.md](11-audit.md): system and
  static complexity.
- `source`: `refs/xboxrecomp/src/kernel/xbox_memory_layout.c` (`xbox_HeapAlloc`,
  `xbox_HeapFree`), `xbox_memory_layout.h` (RAM constants),
  `refs/xboxrecomp/src/kernel/kernel_memory.c` (`MmQueryStatistics`),
  `refs/xboxrecomp/src/kernel/kernel_bridge.c` (`XboxHardwareInfo`),
  `refs/xboxrecomp/src/apu/apu_dsp.c` (DSP stubs),
  `recomp/game/src/main.c` (boot configuration).

## Known issues / current status (tracking)

Moved out of `AGENTS.md`; kept here so the instructional doc stays instructional
and issue tracking lives with the audit record.

- **a-mash reaches the first mission** (canonical check passes). The blocker
  was the contiguous arena (64 MB bump allocator, `xbox_memory_layout.c:3334`)
  exhausting because blocks were never freed; the failed alloc returned 0 and a
  caller wrote physical `0x338` = the USB handle arena `0x80000338`, crashing
  `XInputGetState`. `recomp/game/src/main.c` now defaults
  `RECOMP_HEAP_RECLAIM=1`. If a run ever regresses, first check the log for
  `[CONTIG] arena exhausted` and `RECOMP_WATCH=0x80000338`.
- **Frame rate** (measured 2026-10-09, `goto_gameplay`, 25 s median n=24):
  **real gameplay ~24.9 FPS** (was 21.9 before the swizzle fix; the older ~8 FPS
  note predates correct lazy publication). Menu 3D background ~38 FPS. Only
  trust numbers taken after `Game.goto_gameplay()`; the level `.nhc` alone is
  just the start of the load, followed by the loading screen and briefing.
  `RECOMP_KICK_STATS=1` prints `[KICK]`; ~400–450 kicks/s and ~96% walk time
  in *every* phase.
- **Swizzled-texture decode (FIXED 2026-10-09)**: format `0x06` (swizzled
  A8R8G8B8) was 78% of all texture upload bytes and went through a per-texel
  indirect decode callback. `get_texture` (`nv2a_gpu_d3d11.cpp`) now
  bulk-unswizzles `0x06`/`0x07` with `xbox_unswizzle_rect` (`d3d8_swizzle.h`).
  Gameplay +14% (21.9 → 24.9 FPS), texture phase halved. Confirms the general
  rule: measure the phase first — GPU vertex pulling was tried and rejected
  (3–4% **slower**; prep is only ~18% of the interval and pull covers only the
  16% of draws on the vertex-program path). See `docs/17-executor-roadmap.md`.
- **GPU pushes**: the pushbuffer walker now walks GET→PUT the way the hardware
  does (`nv2a_pb_run` in `nv2a_pb_scan.c`, called from `xbox_memory_layout.c`),
  following top-level JUMPs into secondary command buffers and back. This fixed
  the `[GPU] index command rejected (prim 0)` drops (32-cap → 0). `a-mash`
  passes. See MANUAL_PATCHES.md.
- **Pushbuffer-walker crash (FIXED 2026-10-10)**: `nv2a_pb_run` followed
  JUMP/CALL targets (`XBOX_CONTIG_BASE | (t & 0x0FFFFFFF)`) and read
  `*(mem + va)` with no bounds check, terminating only on exact `va == put_va`.
  When the walk desynced from PUT (misparsed packet, unbalanced CALL/RETURN, or
  a wrapped ring) it marched into non-pushbuffer guest RAM; a stray word that
  decoded as a JUMP sent `va` past the 64 MB `XBOX_CONTIG_SIZE` window and the
  next read faulted — `[CRASH] Access violation ... in nv2a_pb_run+0x73`, all-zero
  Xbox regs (host-side fault, not a guest one). Now every read and jump/call
  target is validated against `[XBOX_CONTIG_BASE, +XBOX_CONTIG_SIZE)`; the first
  violation logs `[PB] desync ... resync to PUT` and drops that one kick instead
  of crashing. The signature is present in logs back to 2026-10-08, so it
  long predates the fix. Watch `[PB] desync` / `[PB-UNK]` for the underlying
  stream desync.
- **Input focus (test flake)**: the game window loses keyboard focus after the
  logo videos; `recomp/tests/framework.py` `goto_mission` now `focus()`es before
  every tap (a one-shot focus is not enough), otherwise the title idles into
  `Attract_Mode.vid` and a-mash times out.
- **Render corruption (FIXED)**: root cause was `dma_resolve`
  (`nv2a_pb_exec.c:129`) promoting only a contiguous block's **head**; vertex
  arrays interleave attributes in one allocation, so normal/diffuse/texcoord
  (+0xC/+0x18/+0x1C) were fetched from raw physical addresses — garbage normals,
  magenta diffuse, x87-indefinite (`0xFFC00000`) NaN UVs. Now promotes by range
  via `xbox_ContigOwnsOffset`. `nonfinite texture coordinate` is sanitized to 0
  instead of rejecting the batch. Title screen + mission briefing render
  correctly; `rejected:`/`unsupported batch` counts are 0. See MANUAL_PATCHES.md.
- **Black character face / texture corruption (FIXED)**: the heap base was
  `0x00F80000`, below the 64 MB contiguous window, so a heap VA and a window
  offset were the same number and `dma_resolve`/APU/OHCI had to guess
  (`[DMA-AMBIG]`); a face texture resolved to the window's unrelated bytes.
  Fixed by actually reading `RECOMP_HEAP_BASE` (defaulted in
  `recomp/game/src/main.c` to `0x04000000`): the heap now runs
  `0x04000000..0x08000000` and any number ≥ 64 MB unambiguously means RAM.
  `[DMA-AMBIG]` must stay 0; if `xbox_HeapAlloc: out of memory` appears, raise
  `RECOMP_TOTAL_RAM_MB`, don't lower the base.
- **Audio in-game (FIXED)**: `mcpx_apu_monitor_frame` (`apu_core.c`) memset the
  EP/DSP mixdown in `monitor.frame_buf` before submitting, so only the software
  (Bink/DirectSound) bridge was audible; VP/DSP game audio was silent. It now
  overdubs voices onto the existing buffer and submits one 256-frame window.
  `--only audible` PASSes. See MANUAL_PATCHES.md.
- **Bink FMV stall**: during a video the main thread spins inside the guest
  software YUV→RGB blit `YUV_blit_0031EAE0` (`recomp_0065.c`), call chain
  `cVideoTexture_Update → BinkCopyToBuffer → BinkCopyToBufferRect →
  YUV_blit_32bpp_48 → YUV_blit_0031EAE0`; no framebuffer flips follow. See the
  row loop around `recomp_0065.c:27510` (`esp+0x40` count) and `:27692`.
- **Sound quality (FIXED 2026-10-09)**: the "56k modem" buzz and the cut-off
  clicks are fixed; `--only audible` and `a-mash` PASS. Root causes and fixes:
  - **187.5 Hz comb** (`48000/256`): the frame thread's inactive branch ticked
    `ep_frame_div` + `monitor_frame` WITHOUT running the GP, so the EP reader
    overtook the GP writer and every 256-sample window carried a cursor seam.
    Fix (`apu_core.c`): run the full `se_frame` whenever `XCNTMODE != OFF`
    (transient FECTL TRAPPED/HALTED is fine — the GP just does a no-op frame);
    when truly OFF, advance the clock alone (no DSP runs).
  - **No resampling**: `voice_resample` (`apu_vp.c`) dropped `rate`. Now uses
    the vendored **libsamplerate** (`src/apu/third_party/samplerate/`, wired in
    `src/apu/CMakeLists.txt`; `apu_shim.h` stubs replaced by the real header)
    with a `src_callback_read` callback that pulls via `voice_get_samples`,
    matching xemu. Rejected earlier linear/nearest resampling.
  - **Cut-off / "reload" gaps**: XAudio2 stopped the source on an empty queue and
    required a 4-buffer prefill to restart. Now the source runs permanently
    (`apu_xaudio2.c`); an empty queue just emits silence. `XA2_NUM_BUFS` 8→16
    (~85 ms headroom). `empty_queue_events` counts residual drains.
  - **Cut-off peaks/clicks**: an abruptly cut sound makes the mix step full
    scale to 0 (captured: constant `-10497` for ~3 s then a `+10497` step — the
    "horrible peak"). `apu_declick` (`apu_core.c`) ramps any `|Δsample|>8000`
    discontinuity over 32 samples across window boundaries.
  - `monitor.frame_buf` is now explicitly zeroed on inactive windows, so a stale
    window is never replayed. `apu_mixer_*` still has **zero callers**, so
    `mixer_render` mixes nothing (soft mixer is a no-op).
  - Diagnostic: `RECOMP_APU_WAV=<base>` writes `<base>.emu.raw` (pre-mixer) and
    `<base>.mix.raw` (submitted); `RECOMP_APU_DIAG=1` prints `[XA2]` queue stats.
  See `recomp/docs/17-executor-roadmap.md`.