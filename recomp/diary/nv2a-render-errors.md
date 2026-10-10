# Diary — NV2A render errors (index command rejected / pushbuffer walker)

Task: make the runtime log free of errors and fix the rendering defects, starting
from the `[GPU] index command rejected (prim 0)` storm and the walker's dropped
commands. Rendering is broken until the user says otherwise; this diary tracks
whether a run's log is error-free, not whether a frame "looks right".

Error counts below are pulled from the runtime log with
`/tmp/opencode/errcount.sh` (rg counts). "index-rejected" is display-capped at 32
in the code, so 32 means ">= 32"; the true count is higher.

## 2026-10-10

### R1 — runtime-20261010-145441.log
- Changed: ack-path edits (uncommitted) — `fence_mirrors_snapshot()` taken before
  the walk and `fence_mirrors_tick()` publishes the snapshot (was a live re-read
  after the walk); `nv2a_pb_run` CALL return PC `ret` made `static`.
- Command: `VIRTUAL_ENV=$PWD/.venv-recomp uv run --active python recomp/tests/run.py --user-state --only a-mash`
- Result: PASS (1 passed, 0 failed).
- Errors: index-rejected 32; `[ICALL] Failed to resolve VA 0x00354B77` 1;
  `Mirror 12/16 FAILED (error 487)` 2; `[IRQLWARN]` 20;
  `[FILE] ... FAILED` ~978; `unsupported` 35.
- Note: none of these are new from this change (present in 144047/144417 too).

### R2 — runtime-20261010-145758.log
- Changed: none (same build as R1).
- Command: `python recomp/tests/capture.py --tag fencefix --frames 12 --interval 5`
  (aborted by the user partway).
- Result: aborted.
- Errors: index-rejected 32 (>= 36 actual); ICALL 1; Mirror 2; IRQLWARN 20;
  `[FILE] ... FAILED` 261. No `[PB] desync`, no `[CRASH]`.

### R3 — runtime-20261010-151721.log
- Changed: added a bounded `[BE] BEGIN/END ... idx_count ... prim_before ... va`
  trace gated by `RECOMP_BE_TRACE` in `nv2a_pb_exec.c`.
- Command: `RECOMP_BE_TRACE=1 VIRTUAL_ENV=$PWD/.venv-recomp uv run --active python recomp/tests/run.py --user-state --only a-mash`
- Result: PASS (1 passed, 0 failed).
- Errors: index-rejected 32; ICALL 1; Mirror 2; IRQLWARN 20; `unsupported` 34.
- Finding: every `BEGIN/END` pair shows `idx_count 0` at END (geometry arrives by
  inline/immediate). The rejected index elements arrive with `prim == 0`, i.e.
  after an `END`. No `[PB] desync`. Claude analysis: the walker drops commands
  (a packet crossing PUT via the `va == put_va` break, plus the non-hardware
  8-zero-word "ring tail" stop), and its method mask accepts reserved commands;
  xemu keeps method/subch/count/noninc across kicks and runs until GET==PUT.

### R4 — after walker rewrite
- Changed (`nv2a_pb_scan.c`): rewrote `nv2a_pb_run` to match xemu's PFIFO pusher:
  persistent `DMA_STATE` (`st`: method/subch/count/noninc) so a packet crossing
  PUT resumes next kick; exact RETURN match (`w == 0x00020000`); method mask
  `0xE0030003` (0 or `0x40000000`) so reserved commands desync instead of
  executing; removed the `va == put_va` mid-packet break and the 8-zero-word
  "ring tail" stop. Fixed `NV097_NAMES`: `0x1808` is `ARRAY_ELEMENT32` (was
  mislabelled `INLINE_ARRAY`); added `0x1818 INLINE_ARRAY`.
- Command: `RECOMP_BE_TRACE=1 VIRTUAL_ENV=$PWD/.venv-recomp uv run --active python recomp/tests/run.py --user-state --only a-mash`
- Result: PASS (1 passed, 0 failed).
- Errors: **index-rejected 0** (was >=32), **`unsupported` 0** (was 34), no
  `[PB] desync`, no `[PB-UNK]`, no `[CRASH]`/RAMHT, no `reserved command`.
- Remaining errors: `[FILE] ... FAILED` 978, `[IRQLWARN]` 20,
  `Mirror 12/16 FAILED (error 487)` 2, `[ICALL] Failed to resolve VA 0x00354B77` 1.
- Regressed: nothing observed.

### R5 — after the four-error pass
- Changed:
  - `kernel_bridge.c`: `[FILE]` probe results — the two exact not-found pairs
    (`0xC0000034`+err2, `0xC000003A`+err3) now print `(absent; returned to
    title)` instead of `FAILED`; any other pairing still prints `FAILED`.
  - `xbox_memory_layout.c`: skip (don't fail) the mirror that overlaps the
    contiguous window at `0x80000000`; the one that cannot map because a host
    range is in use is reported as `not mapped ... left unbacked` instead of
    `FAILED`.
  - `kernel_hal.c`: the IRQL level of a host ISR/DPC is now per host thread
    (`RECOMP_TLS t_isr_irql`) instead of swapping the shared `g_cpu_irql`; the
    guest's shared level is untouched. `irql_publish`, `xbox_IrqlBlocksInterrupts`
    and `xbox_IrqlRaisedCount` account for `g_isr_active`.
- Command: `VIRTUAL_ENV=$PWD/.venv-recomp uv run --active python recomp/tests/run.py --user-state --only a-mash`
- Result: PASS (1 passed, 0 failed).
- Errors: index-rejected 0, `unsupported` 0, `[IRQLWARN]` 0, `Mirror ... FAILED`
  0, `[FILE] ... FAILED` 0. Remaining: `[ICALL] Failed to resolve VA 0x00354B77` 1.
  GPU stat lines read `0 failures` / `0 rejected` (not errors).
- Regressed: nothing observed.

### R6 — baseline: replay `userplay` — runtime-20261010-162311.log
- Changed: none (walker with window bounds check).
- Command: `make replay-session SESSION=userplay`
- Result: FAIL. `[PB] desync` 8, `[PB] walk budget exhausted` 27,
  `index command rejected` present (rejected 242 lines), `unsupported` 42,
  `semaphore release failed` 1 (that path `_Exit`s), `[CRASH]` 0.
- Diagnosis of first desync (log :44607, kick get 8004EAA4 put 800567EC):
  stream parses cleanly; walk 8004EAA4..80055408, JUMP 020F5001 into a
  `RunPushBuffer` buffer (BEGIN / 0x1800 x249 / END), its tail JUMP 00057181
  returns to 80057180 -- PAST PUT -- so `va == put` never matches. Tail was
  re-patched by a 2nd `D3DDevice_RunPushBuffer` (0x2CC590) at ring 0x5717C,
  which took the "push buffer idle" path because `pb->Lock (= [dev+0x2C])`
  <= GPU time, and the GPU time had been overwritten by `fence_mirrors_tick`
  with `[dev+0x2C]` = D3D's NEXT fence (SetFence writes T then sets 0x2C=T+2).

### R7 — fence mirror gated off under native fences — runtime-20261010-163610.log
- Changed: `xbox_memory_layout.c` `fence_mirrors_tick` returns when
  `xbox_Nv2aNativeFencesEnabled()` (executor's 0x1D70 release is the GPU time).
- Command: `make replay-session SESSION=userplay` (stopped after ~4 min)
- Result: improved, not clean. `[PB] desync` **0** (was 8), walk budget
  exhausted **13** (was 27), `index command rejected` 3, `[IRQLWARN]` 1,
  `unhandled` 15 lines, `semaphore release failed` 0, `[CRASH]` 0.
- Remaining hypothesis: the busy path of RunPushBuffer patches the tail via NOP
  0x0100 software method types 0xC/0xD/0xE (CMiniport::SoftwareMethod ->
  FixupPushBuffer); the executor dispatches 0x0100 *deferred* (and drops it if
  another is pending), so the walker reaches the stale tail and loops.
### R8 — walker models JUMP-into-buffer as a call — runtime-20261010-195549.log
- Changed: `nv2a_pb_scan.c` `nv2a_pb_run`. D3D8 draws compiled geometry by
  JUMPing into a shared buffer that ends in a JUMP back to the caller; the
  title rewrites that exit word per use (via the 0x0100 FixupPushBuffer software
  method, which the deferred executor can drop). A GET->PUT batch walk reads
  final memory and sees only the first caller's return, so every other caller
  looped back to the first forever -> budget exhausted -> dropped kick.
  Fix: an out-of-line forward JUMP (target on a different 64 KB page, forward)
  pushes a return PC; a backward cross-page JUMP with one pending returns to it
  (a real CALL still uses `ret`; a backward JUMP with nothing pending is a ring
  wrap). Depth 4. `MANUAL_PATCHES.md` not affected (runtime source).
- Verified offline first: a simulator over the captured FULL KICK dump
  (`/tmp/opencode/simwalk.py`) shows CALL 80133FB4 -> RET 80133FB8,
  CALL 80135054 -> RET 80135058 (was looping to 80133FB8).
- Commands: `bash recomp/game/build.sh`;
  `recomp/tests/run.py --user-state --only a-mash` -> **PASS (1 passed)**;
  `REPLAY=1 SESSION=geom-crash scripts/18-launch-user.sh` (the exact recording
  that crashed), stopped after ~180 s (recording ~155 s), 8166 flips.
- Result on replay: `[PB] walk budget exhausted` **0** (was 25),
  `[PB] desync` **0**, `index command rejected` 18 (was 22), `unhandled` 18
  (was 15), `FAILED` 0, `[CRASH]` 0. a-mash run: budget 0, desync 0,
  rejected 4, unhandled 4.
- Regressed: nothing observed. Remaining: the 0x0100 FixupPushBuffer software
  method is still dropped by the deferred executor; the walker no longer needs
  it, but any CPU-visible tail patch it performs is still not applied.
