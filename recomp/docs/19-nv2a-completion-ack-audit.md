# 19 — NV2A completion-ack audit: the root cause of the memory corruption

Author: workspace agent, 2026-10-10. Consult: Claude Opus 5.5
(`/tmp/opencode/ask-claude-20261010-142258.log`), plus an independent read of
`refs/xboxrecomp` and the xemu PFIFO pusher (`hw/xbox/nv2a/pfifo.c`).

## TL;DR

The corruption was not a pushbuffer-parsing bug. It was a **false GPU-completion
acknowledgement**: `fence_mirrors_tick()` runs at the top of the NV2A tick
(`xbox_memory_layout.c:1121`), **before** the pushbuffer walk has executed
anything, and copies the device's *issued* fence value (`[dev+0x2C]`) into the
fence the guest polls. D3D therefore believes every GPU command has retired and
immediately reuses / refills / frees ring space and dynamic buffers — including
font glyph quads and vertex buffers — while the ack thread is still walking and
executing them. The walk then reads half-overwritten memory: a long run of
zeroed words with a stale word left over that decodes as a JUMP, which the
walker follows into non-command memory, executing garbage methods (the
`RAMHT object unavailable: handle 0xFF000000` fault).

This is the *same bug class* the code already documents and fixed for `DMA_GET`
at `xbox_memory_layout.c:1108-1120` ("GET used to be set to DMA_PUT here, at the
top of the tick, before the scan below had executed anything … a lost-command
race"). The fix was applied to the DMA_GET advance but **not** to the completion
fence/event, which still advance before execution.

## The execution model (where the boundary is)

- Guest D3D8 builds command streams in a ring, writes them through the USER
  DMA window and advances `USER_DMA_PUT` (`xbox_memory_layout.c:291`).
- On a `PUT` change the runtime walks the ring from a persistent GET
  (`s_get` = previous PUT) to the new PUT, decoding NV2A method packets
  (increasing / non-increasing), following JUMP / CALL / RETURN, and **executing
  each method immediately** via `nv2a_pb_exec_method` into the native D3D11
  backend (`nv2a_pb_scan.c:297` `nv2a_pb_run`; kick site
  `xbox_memory_layout.c:1189-1194`).
- After the walk it latches `DMA_GET = PUT` (`:1258-1263`) so the guest gets
  back-pressure (it can only reuse space behind GET).

This GET->PUT walk is the correct model: xemu's pusher processes exactly
`[DMA_GET, DMA_PUT)`, follows JUMP/CALL, and stops only at PUT
(`hw/xbox/nv2a/pfifo.c`, function `pfifo_run_pusher`). On hardware a pushbuffer
is an area the CPU fills and tells PFIFO to process; the CPU sets PUT to point
**right after the last word it wrote**, so `[GET, PUT)` is always valid
commands. (envytools `docs/hw/fifo/dma-pusher.rst`.)

## Findings, ranked

1. **False completion ack (root cause).** `fence_mirrors_tick()`
   (`xbox_memory_layout.c:895`) is called at `:1121` — before the walk — and
   again at `:1284`. The `:1121` call writes the issued fence into the polled
   fence before execution. `event_signals_tick()` (`:958`, called `:1285`)
   signals D3D's retire event (`dev+0x1DCC`) every tick unconditionally.

2. **An honest mechanism already exists and is on by default.** Native fences
   (`RECOMP_NV2A_NATIVE_FENCES=1`, defaulted in `recomp/game/src/main.c:271`)
   make `semaphore_release` (method `0x1D70`, `nv2a_pb_exec.c:550`) write the
   command's value to its semaphore destination **when the walk reaches it**
   (`nv2a_pb_exec.c:3611-3614`). So the executed-work ack is already
   implemented; the per-tick fence mirror and event signal run *on top* and
   race ahead of it.

3. **Cross-thread.** The NV2A tick runs on the ack thread; the guest runs on its
   own thread. The window between `:1121` (fence advanced) and `:1194` (walk
   executes) is a real window in which the guest reuses the ring.

4. **`ret` does not survive a kick.** The CALL return address is a local in
   `nv2a_pb_run` (`nv2a_pb_scan.c:301`; hardware keeps it in
   `DMA_SUBROUTINE`, `0x324C`). An in-flight CALL at a kick boundary is lost.

5. **Ring wrap and `dma_limit`.** A wrap is just a JUMP and is handled. The
   64 MB contiguous-window check is about as strong as modelling `dma_limit`
   (the pushbuffer DMA object covers all of RAM), so it is a weak guard.

## Evidence

- A large kick `[0x8018C1D0, 0x80193678)` decodes as a **self-consistent** NV2A
  method stream for its first ~1671 words (inline vertex data: non-increasing
  method `0x1818` with 28 params, method `0x17FC` with 1 param — addresses
  line up exactly with the decoded counts), then ~1671 words of `0x00000000`
  (each a 0-count NOP), containing one stale word `0x01A93001` that decodes as
  JUMP to `0x81A93000`. Following it executes garbage -> RAMHT fault.
- PUT advances monotonically in small steps (a lap in progress), so the zero
  region is genuinely inside `[GET, PUT)` — i.e. the memory was **changed after
  it was written**, matching early reuse (finding 1), not a misparse.
- The same binary renders a skinned character fully textured at 640x480 but
  black/untextured at 1280x720, and garbles a font-atlas UI glyph. Both are
  timely reuse of memory the GPU has not retired (font glyph quads are dynamic
  vertex buffers D3D refills once it believes the previous frame retired), and
  the resolution dependence is a timing/allocator-layout shift, not a separate
  format bug.

## What I did wrong (patch-on-patch history)

The user reported the corruption when it appeared. Instead of auditing the
completion path I added walker guards on top of the symptom:

- `8dafb3a` window bounds check (prevents a host access violation, keeps the
  desync) — necessary but only masks the crash.
- `480f795` stop the method payload loop at PUT + packet dump.
- (uncommitted) "reject a jump target past PUT" — too aggressive; it **drops
  whole kicks**, which is why the guard build rendered the character black and
  the glyphs garbled.
- (uncommitted) "stop at a run of 0x00000000 headers (unwritten ring tail)" —
  also a symptom patch; on its own it stops the crash but does not stop the
  guest reusing memory.

None of these fix the cause: the guest is told work is done before it is.

## Fix

Report GPU completion only from executed work.

1. **Remove the pre-walk `fence_mirrors_tick()` at `xbox_memory_layout.c:1121`.**
   The post-walk call at `:1284` already exists; the pre-walk call is the exact
   mistake the `:1108-1120` comment describes for DMA_GET.
2. **Gate `fence_mirrors_tick` and `event_signals_tick` off when native fences
   are enabled** (native fences are the honest ack). Verify the `0x1D70`
   semaphore destination is the fence the guest polls, and that D3D's retire
   event still gets signalled when the release executes (otherwise
   `D3D::BlockOnTime` hangs, `xbox_memory_layout.c:924-934`).
3. **Make `ret` static** in `nv2a_pb_run` (survive a kick boundary, like
   `s_get`).
4. Once verified, remove the symptom guards (past-PUT / zero-tail stop) if the
   bounds check plus the honest ack suffice; keep the bounds check and the
   packet diagnostic.

## Verification (user profile, 720p, no human)

- `recomp/tests/capture.py --tag <t>` launches `scripts/18-launch-user.sh`
  (1280x720 KBM) and saves BMP+PNG frames under
  `recomp/tests/baselines/captures/<t>/`; `--diff <a> <b>` reports mean absolute
  pixel error and percent over tolerance (`recomp/tests/fbtool.py` does the
  BMP->PNG + diff, stdlib only — no PIL/ImageMagick on this host).
- `python3 recomp/tests/run.py --user-state --only a-mash` must PASS with
  `[PB] desync` / `[PB-UNK]` = 0 and no `RAMHT object unavailable`.
- The captured title-screen character must be textured (visually, and
  `pct_over_tol` vs a pre-regression capture near 0).

## Open questions

- Does `semaphore_release`'s destination equal the polled fence, or is the
  mirror still required (just moved after the walk)?
- With native fences on and both ticks gated, does D3D still get its retire
  event, or must `semaphore_release` signal it explicitly?
- If corruption survives the ack fix: snapshot the segment at kick time vs walk
  time to prove concurrent overwrite; `RECOMP_WATCH` the zero-tail range and log
  `RECOMP_HEAP_RECLAIM` frees; dump texture state (`0x1B00`+) at 720p vs 480p.

## References

- `refs/xboxrecomp/src/kernel/xbox_memory_layout.c`: `fence_mirrors_tick:895`,
  `event_signals_tick:958`, the `:1108-1120` DMA_GET comment, call sites
  `:1121` and `:1284-1285`, walk kick `:1189-1194`, GET latch `:1258-1263`.
- `refs/xboxrecomp/src/kernel/nv2a_pb_scan.c`: `nv2a_pb_run:297`, `ret:301`.
- `refs/xboxrecomp/src/kernel/nv2a_pb_exec.c`: `semaphore_release:550`,
  `xbox_Nv2aNativeFencesEnabled:510`, dispatch `:3595-3614`.
- `recomp/game/src/main.c`: native fences default `:271`, mirror/event
  registration `:369-371`.
- xemu `hw/xbox/nv2a/pfifo.c` (`pfifo_run_pusher`); envytools
  `docs/hw/fifo/dma-pusher.rst`.