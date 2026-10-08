# Manual patches to generated code

`scripts/20-regen-recomp.sh` **overwrites** `src/recomp/gen/*` from
`refs/xboxrecomp`. Every hand-edit below is lost on the next regen and must be
re-applied (or, better, fixed in the lifter/templates in `refs/xboxrecomp`).

## RESOLVED: contiguous arena exhaustion crashed the input poll

Symptom: a-mash died with an access violation in the guest XAPI
`XInputGetState_8_0035A9A1` (`recomp_0068.c:2616`), reading `[handle]` =
`0xEAFE0000` (a TD/ED control word) at `0x80000338`. `RECOMP_WATCH=0x80000338`
showed a guest store of float/texture data there, right after repeated
`[CONTIG] arena exhausted (…, 66969600 of 67108864 used)`.

Root cause: `xbox_ContiguousAlloc` (`refs/xboxrecomp/src/kernel/
xbox_memory_layout.c:3334`) is a monotonic bump allocator; without
`RECOMP_HEAP_RECLAIM` blocks are never freed (framebuffers), so the 64 MB
window fills. On exhaustion it returns **0**, and a caller that ignores the
failure writes to physical `0x338`, which aliases the XDK USB handle arena at
`0x80000338` — corrupting the controller handle.

Fix: default `RECOMP_HEAP_RECLAIM=1` in `recomp/game/src/main.c` (after the
`RECOMP_VBLANK` default). The canonical check
`python3 recomp/tests/run.py --user-state --only a-mash` now **PASSES**
(reaches the first mission). Durable fix, if reclaim ever proves unsafe for
framebuffers: make callers of `xbox_ContiguousAlloc` check for 0.

## `src/recomp/gen/recomp_0065.c` — `YUV_blit_0031EAE0` (active fix)

Bink FMV hang: the row loop spun forever because a skipped indirect call left
`esp` 4 bytes low.

- `loc_0031EE3D` (~27631) and `loc_0031EE45` (~27639):
  `uint32_t _icall_esp = g_esp;` → `uint32_t _icall_esp = g_esp + 4;`
- Why: the guest `push esi` (lifted at ~27626) is a stdcall argument shared by
  both indirect calls. The lifter captured `_icall_esp` **after** that push, so
  `RECOMP_ICALL_SAFE_AT`'s not-code path (`g_esp = saved_esp`) only popped the
  return address, not `esi`. With `+4` the not-code path pops the arg too.
- Not-code target is `0x00000000`: `[0x4C07C0]`/`[0x4C07E8]` are set by
  `setevenodd_0031E660` from a descriptor (`ebx+0x18`/`ebx+0x10`/`ebx+4`/`ebx+0x20`)
  and are 0 here. Fixing esp stops the hang; the blit itself is still skipped
  (frame won't render). Root cause of the null descriptor TBD.

## `src/recomp/gen/recomp_0046.c` — `check_for_MMX_0022AA10` (MMX present)

Root cause of the NULL Bink YUV blit: `setevenodd_0031E660` early-exits when
`0x4C9BE8` (MMX-blitters flag) is 0, so `0x4C07C0`/`0x4C07E8` stay 0.
`check_for_MMX` detects MMX via `pushfd`/`cpuid`, which the lifter emits as
`RECOMP_UNIMPL` no-ops, so the flag is always 0. The Xbox is a Pentium III, so
MMX is always present.

- `loc_0022AA1E` (~4624): first statement `MEM32(ebp + -4) = 1;
  goto loc_0022AA50;` before the (dead) `pushfd`/`cpuid` sequence. The epilogue
  at `loc_0022AA79` does `esp = ebp`, so skipping the pushes is stack-safe.
- Durable fix: teach the lifter to model `cpuid` (fixed P-III values) and
  `pushfd`/`popfd`. Other unlifted `cpuid` sites: `0x11A414` (`recomp_0024.c`),
  `0x2E246B` (`recomp_0061.c`).

## `src/recomp/gen/recomp_0043.c` — `cVideoTexture_Update_00206030` (bounded decode)

- `int _decode_iters = 0;` (~31086)
- `if (CMP_EQ(_fa, _fb) && ++_decode_iters < 4) goto loc_00206050;` (~31158)
- Caps the decode retry so a stuck video frame yields instead of spinning.

## Diagnostics (temporary — remove once resolved)

- `refs/xboxrecomp/src/kernel/nv2a_gpu_d3d11.cpp` ~2505: prints `[TEXCOORD]`
  (stage/vertex/comp, the 4 texcoord floats, `state->texgen`, `texture_matrix_enable`)
  before the `nonfinite texture coordinate` reject. Remove when done.
- `refs/xboxrecomp/src/kernel/nv2a_pb_exec.c` ~2876: the `unsupported batch`
  path no longer calls `_Exit(EXIT_FAILURE)` — it logs once (≤32) and skips the
  batch, so a rejected draw costs a frame instead of killing the run. Revert or
  gate when the backend handles the batches.
- `refs/xboxrecomp/src/kernel/nv2a_pb_exec.c` ~3714: `[TEX1]` logs stage-1
  texture method writes. Remove when done.
- `refs/xboxrecomp/src/kernel/nv2a_pb_exec.c` ~3296: `require_index_capacity`
  now returns `int` and, when `prim == 0`, logs ≤32× and returns 0 instead of
  `_Exit`; callers at 3103/3156/3342/3946/3955/3962 guard on it. Same
  "unsupported batch" treatment.
- `refs/xboxrecomp/src/kernel/nv2a_pb_scan.c` ~220: `[PB-UNK]` logs undecoded
  packet words (decoder-sync diagnosis). Fired 0× in the last run, so the
  prim-0 index commands are NOT a misread header.

### Pushbuffer walker: GET→PUT, follows jumps to secondary buffers (FIXED)

Root cause of the `index command rejected (prim 0)` and `nonfinite texture
coordinate` rejects: `pb_walk` broke at the first top-level JUMP, but D3D8's
top-level `0x...01` words are real JUMPs to **secondary command buffers that
hold the batch** — verified: a jump at `0x80191F90` to `0x81133000` where the
target is `000417FC` (BEGIN, prim 6), `41181800` (ARRAY_ELEMENT16) + indices,
and the buffer jumps back to `0x80191F94` (ring jump + 4). Breaking there
dropped every draw in the buffer, leaving stale vertex-array state so later
array elements arrived with `prim 0` and raw NaN UVs.

Fix (`refs/xboxrecomp`, survives regen): replaced the fixed-range `nv2a_pb_scan`
calls + wrap/`put_lo`/`put_hi` guessing in `xbox_memory_layout.c:1103` with a
hardware-faithful walker `nv2a_pb_run(put)` in `nv2a_pb_scan.c`:

- persistent `s_get` (GPU GET) walked to `put`, following every JUMP
  (in/out of the ring) and CALL (one return level); RETURN restores the PC.
- first kick only latches `s_get = put`; the ring's first submission runs on
  the next kick (without this the GPU bootstrap block `0x2000→0x2280` never
  executed and boot `_Exit`ed on `semaphore release failed`).
- top-level RETURN with no pending CALL is a no-op (was taking it to address
  0 and walking the fake TIB).
- `budget` 0x200000 words, then resync to PUT; `[PB-UNK]` still logs.
- the ring wrap is just another jump, so `s_last_jump`/`nv2a_pb_last_jump` are
  no longer needed by the caller (kept, harmless).

Verified: `a-mash` reaches the first mission; `index command rejected (prim 0)`
drops from the 32-cap to **0**. Frame rate is unchanged by the walker (menu
35+ FPS, in-game 20–40 FPS) — the walker is not the slowdown.

### Vertex arrays: `dma_resolve` promoted only the block head (FIXED)

Root cause of the remaining render corruption (magenta polys, dark model, NaN
UVs). `dma_resolve` (`nv2a_pb_exec.c:129`) tested
`xbox_ContiguousBlockSize(XBOX_CONTIG_BASE + offset)`, which matches only a
block's **head** address. A game vertex array interleaves its attributes in one
allocation (position `0x81085000`, normal `+0x0C`, diffuse `+0x18`, texcoord
`+0x1C`); only the position (the head) promoted to the window, so normal /
diffuse / texcoord were fetched from raw physical addresses holding unrelated
bytes — garbage normals (dark unlit model), magenta diffuse, `0xFFC00000`
(x87 "indefinite" NaN) UVs. `[TEXVTX]` confirmed the head read valid data while
`[TEXNAN]` at the same nominal address read NaN.

Fix: promote on ownership **by range** — `xbox_ContigOwnsOffset(offset)`
(`xbox_memory_layout.c:3525`, `contig_block_at`), which already existed but was
unused. Behavior for surfaces (heads) is unchanged. Verified: title screen and
mission briefing render correctly; all `rejected:` / `unsupported batch` counts
go to 0; menu/a-mash FPS rises (8.5 → 12.3).

### `nonfinite texture coordinate`: sanitize, don't reject

`nv2a_gpu_d3d11.cpp:2504`: hardware does not reject a NaN/inf texcoord — it
samples texel 0 — so dropping the whole batch deleted geometry. Now the bad
component is folded to `0.0f` and the draw continues (`nv2a_gpu_draw`'s vertex
parameter dropped `const`; the array is a mutable scratch buffer).

Removed temporary diagnostics: `[PB-JMP]`, `[PB-JTGT]`, `[PB-BEGINSEEN]`,
`[PB-GAP]`/`[PB-DUMP]`, `g_last_begin_va`/`g_last_end_va`. Kept `[PBRING]` and
`g_pb_current_va`.

## `recomp/tests/framework.py` — focus the user-state window (a-mash flake)

`_start_user_state` (and the non-user-state path already did) now calls
`self.focus()` after the boot wait. Without it the a-mash test times out: the
game renders (~35 FPS) but never leaves the menu, `[INPUT]` shows
`window_has_SPACE=1` (the diag reads the global keymap) yet `InputGetState=0`
and `buttons=0`, because `xinject` delivers keys only to the focused window and
the user-state launch never focused it. With the call, `a-mash` passes
reliably. (mutter reverts plain `XSetInputFocus`; `xinject focus` handles that.)

Still-fatal `_Exit` sites to consider (per Claude): nv2a_pb_exec.c:958/980
(vertex attr), 3769 (unsupported state program). Keep 515/3417/3422/3440
(fence/RAMHT/checkpoint — skipping hangs the guest) and 2481/3316/3322
(clock/OOM).

## Not in gen/ (survive regen) — `refs/xboxrecomp`

Recorded for completeness; these live in the runtime repo, not regenerated:

- `src/kernel/nv2a_pb_exec.c`: restored pre-`794d9a5` native-D3D11 integration,
  `0x0100` → `xbox_Nv2aSoftwareMethodDeferred` (sync variant deadlocks).
- `src/kernel/kernel_bridge.c`: `xbox_Nv2aSoftwareMethodDeferred`.
- `src/usb/ohci.c`, `src/input/xinput_device.c`, `src/usb/usb_gamepad.c`:
  OHCI `pad_live` + per-CPU IRQL + `[INPUT]` diag.
- `src/kernel/nv2a_gpu_d3d11.cpp:2504`: `nonfinite texture coordinate` now
  checks a component only when `state->texgen[stage][component] == 0`. When
  texgen generates s/t/r (e.g. `0x8512` normal map) the raw texcoord is unused
  and `texcoord_attr()`'s "first float2" fallback can hold junk; the old check
  rejected the whole batch on that junk. Texgen-off NaN components are now
  sanitized to 0 rather than rejecting the batch (see the section above).
- `src/kernel/nv2a_pb_exec.c:129` `dma_resolve`: promote by range via
  `xbox_ContigOwnsOffset`, not `xbox_ContiguousBlockSize` head-only.
- `src/kernel/xbox_memory_layout.c`: `RECOMP_HEAP_BASE` is now actually read
  (`main.c` had defaulted it to `0x04000000` but nothing consumed it). Heap
  VAs are identity-"physical", so a heap below 64 MB shared numbers with
  contiguous-window offsets and `dma_resolve`/APU/OHCI had to guess
  (`[DMA-AMBIG]`, black face texture). Heap is now `0x04000000..0x08000000`
  (64 MB). If `xbox_HeapAlloc: out of memory` shows up, raise
  `RECOMP_TOTAL_RAM_MB`, and don't lower the base. `RECOMP_HEAP_BASE=0` restores
  the old layout for A/B tests.
- `src/apu/apu_core.c` `mcpx_apu_phys`: no 64 MB wrap for addresses inside the
  mapped RAM, since heap sample buffers now live above 64 MB.
- `nv2a_pb_exec.c` `[DMA-AMBIG]`: counter now counts only ambiguous hits (it
  used to count every promotion, so it went silent after 256).