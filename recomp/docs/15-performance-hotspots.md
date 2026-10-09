# 15 — Performance hotspots: the in-mission CPU profile

Audit of where host CPU actually goes while the recompiled build runs the first
mission (`1_3_1b_Hive_StationOuter`). This supersedes the earlier
menu-focused budget in [09-performance.md](09-performance.md) with a real
host-sampled, symbolicated profile of in-mission gameplay.

**Target: 45 FPS. Baseline: ~10–23 FPS in-mission.**

## How this was measured

Plain `perf` cannot symbolicate this process: Wine maps the `ghost.exe` PE as an
anonymous executable region, so every sample is labelled `[JIT]` and no function
names appear. The tooling added here fixes that:

| Artefact | Purpose |
|---|---|
| `scripts/21-profile-recomp.sh` | wrapper: drives the game to the mission, records, symbolicates |
| `scripts/profile-recomp.py` | reusable driver + symbolizer (`--symbolize-only` on an existing perf.data) |
| `recomp/tests/test_performance.py` | persistent test: reach the mission, measure FPS/frame advance |
| `framework.Game.goto_gameplay` | canonical A-mash until the map name is in the log, then 5 s settle |

`profile-recomp.py` symbolicates by locating the anonymous executable mapping
that holds the sample IPs (the PE's ASLR-chosen load base), converting each IP
to a PE RVA (`IP − base + 0x140000000`), and resolving it with `llvm-symbolizer`
against `recomp/game/build/ghost.exe` (which auto-loads `ghost.pdb`).

Reproduce:

```
scripts/16-stop-recomp.sh
scripts/21-profile-recomp.sh --secs 30
# -> /tmp/opencode/perf-recomp.data + .report.txt
```

## Evidence

Representative run: 32,656 `cpu-clock` samples over 30 s of gameplay,
28,216 (86%) inside the PE image. Top self-samples:

| % | Function | Kind |
|---:|---|---|
| **34.8%** | `D3D_ComputeGap_002C5EA0` | guest: fence busy-wait (see Step 1) |
| 6.0% | `apu_mmio_rd` / `mmio_emulate` (`apu_mmio_hook.c`) | runtime: APU MMIO VEH |
| 5.4% | `fb_exit_process` (`video/fb_present.c`) | runtime: framebuffer present |
| 4.3% | `bcmp` (`compiler_rt`) | runtime: texture validate (`memcmp`) |
| 3.1% | `recomp_fp_round24` | runtime: x87 rounding helper for recompiled FP |
| 2.4% | `gpu_submit_chunk` (`nv2a_pb_exec.c`) | runtime: pushbuffer execution |
| 2.1% | `D3DDevice_Clear_24_002C9090` | guest: D3D clear |
| **~11–13% combined** | `dsp_cpu.c`, `dsp_emu.c.inc`, `dsp_dis.c.inc`, `dsp_mul56`, `dsp56k_read_memory`, `emu_*` | runtime: **DSP56300 interpreter** (see Step 2) |
| 7.4% | `d3d/d3d8_resources.c` | runtime: D3D8 resource shim |
| 3.8% | `kernel/nv2a_pb_exec.c` | runtime: pushbuffer walker |

Per-thread: the guest main Win32 thread spends ~93% of its own samples inside
`D3D_ComputeGap_002C5EA0`; the DSP interpreter and GPU/APU work is on worker
threads. So the frame loop is *waiting*, and the CPU is busy in a spin, not in
useful work.

## Step 1 — `D3D_ComputeGap_002C5EA0` = 34.8% (guest fence busy-wait)

It is *not* a heavy function. `D3D_ComputeGap` is a 21-instruction leaf
(`recomp_0059.c:15738`, original `0x002C5EA0`, 47 bytes):

```
Signature: unsigned long D3D::ComputeGap(D3D::CDevice *, D3D::Fence *,
                                         unsigned long volatile *)
```

It returns how far the GPU is behind a target pushbuffer position, clamped to
zero. It is the inner call of the guest's software-D3D **flow-control
busy-wait**, `D3D::BlockOnTime` (`recomp_0059.c:16847`, `D3D_BlockOnTime_002C6490`,
`0x002C6490`):

```
v = D3D::GpuGetOrNewer(dev, ...)        ; 0x2C61B0  read GPU write pointer
gap = D3D::ComputeGap(dev, fence, &v)   ; 0x2C5EA0  how far the GPU is behind
if (gap >= 0x2000) D3D::FlushWCCache()  ; 0x2C6230  ring not drained: flush/retry
```

`D3D::BlockOnTime` is called from essentially every D3D device path and from the
present/swap path (`recomp_0060.c:16215`, original `0x002CF150`). The guest
generates commands (~815 draws/frame) as fast as it can and then **spins** (the
caller re-enters the wait until the ring drains) until the emulated GPU has
consumed enough of the ring. The runtime advances the GPU read pointer when
`nv2a_pb_run` drains the pushbuffer and the D3D11 submissions complete — so how
long the guest spins is set by the runtime's completion/fence signalling.

This is the same wall already visible from the runtime side
([09-performance.md](09-performance.md) §4.2): completion-event waits dominate
the runtime interval (colour readback + depth publish every flip). The host
profile shows the *other* end of that wait — the guest burning a core polling it.

**Ranked first because it is the largest single cost and it is pure stall.**
Directions (to be measured, not assumed):
- Reduce flip-path work so the GPU read pointer advances sooner: defer/drop the
  full-frame colour readback and depth publish on every flip (§4.2), or gate them
  on actual guest reads.
- Complete D3D11 submissions / fences faster or off the critical path (check
  `gpu_sync_impl`, completion-event cadence, `RECOMP_SYNC_LIGHT` behaviour).
- Fewer `BlockOnTime` stalls per frame (less redundant state/buffer-wait churn).
- Confirm the 0x2000 threshold and ring size are not forcing extra round trips.

## Step 2 — DSP56300 interpreter ~11–13% (runtime APU)

The GP and EP audio DSPs are emulated with a **per-instruction DSP56300
interpreter** ported from xemu/Hatari:
`src/apu/dsp/dsp_cpu.c` (`dsp56k_execute_instruction`), `dsp_emu.c.inc` (239 KB
of opcode implementations), `dsp_dis.c.inc`, `dsp_dma.c`.

It runs every APU frame in `apu_dsp.c:668–716` `dsp_frame_engine()`:
- VP mixbins are written into GP X memory (`:657–663`),
- `do { dsp_run(d->gp.dsp, 1000); } while (!is_idle && realtime);` (`:674–676`),
- same for EP at `:705–707`.

**It is on by default.** `apu_dsp_engine_enabled()` (`apu_dsp.c:45–53`) returns
true unless `RECOMP_APU_DSP=0`. Rationale (`apu_dsp.c:55–61`): DirectSound init
spins until the GP DSP program writes a zero acknowledgement word back, so the
passthrough stub needs `RECOMP_APU_DSP_ACK` to fake it or the title hangs.

**Documentation drift:** `apu/README.md:6–7` and `:56–57`, and the file header at
`apu_dsp.c:11` still describe GP/EP as "stubbed — passthrough". The interpreter
is the default path (`apu_dsp.c:6–9,42–44`). This needs correcting.

Directions:
1. Measure whether the title needs the engine: `RECOMP_APU_DSP=0`
   `RECOMP_APU_DSP_ACK=gp:0x810`, verify `run.py --user-state --only audible`,
   and compare FPS. If audio holds, defaulting off removes the whole cost.
2. If it is needed: decoded-opcode cache (`pram_opcache` already exists), skip
   re-running when the guest program/inputs are unchanged, run only the processor
   whose program was actually downloaded, shrink the per-frame cycle budget.
3. Long term: AOT-lift the DSP program the way the game's x86 is lifted.

## Busy-wait handling — the #1 emulator performance class

Guest busy-waits are the single most common source of "why is this emulator
slow": the guest polls a value that only the emulator's device model can change,
and the emulator burns a core (or starves the device thread) until it does. Every
mature emulator has an explicit remedy:

| Project | Mechanism |
|---|---|
| Dolphin (PPC) | `PPCAnalyzer::IsBusyWaitLoop` classifies a block whose backward branch closes a loop that only loads + compares; on hit it calls `CoreTiming::Idle()` to skip to the next scheduled event (JIT `branchIsIdleLoop` / `WriteIdleExit`, cached interpreter `CheckIdle`). |
| PCSX2 (MIPS) | `WaitLoop` speedhack: on a tight branch-to-self, `intUpdateCPUCycles()` then advance `cpuRegs.cycle` to `cpuRegs.nextEventCycle`. |
| Ymir (SH-2/1) | Optional idle-loop detector: skip code execution while "stepping the allotted cycle budget", but never skip DMA, and break on interrupts/exceptions. Also invalidate detected loops when memory changes. |
| VMware ESX / Denali / Xen | Binary translation / source instrumentation detects OS idle loops and deschedules the vCPU; hardware spin-detection patents drive VM exits. |
| Intel VMX / KVM | PAUSE-loop exiting; `handle_pause()` yields to the lock-holder vCPU. QEMU `WFI`/`HLT` set `cpu->halted` so the vCPU thread sleeps instead of spinning. |

The common shape: **classify the loop, then stop executing it** — advance the
emulated clock to the next event (or yield), and re-check the polled value only
when that event fires. The correct shortcut is to keep DMA/device work and
interrupts live; only the *empty spin* is elided.

### How this maps onto our hotspot

`D3D_ComputeGap` (Step 1) is the poll inside the guest's D3D pushbuffer
flow-control wait. The loop reads a value that only the runtime's GPU/present
path advances. That is exactly the shape Dolphin/PCSX2 detect. For the
recompiler the analogue is:

1. **Classify** the loop at generation or first execution: a small cycle whose
   only side effects are reads and whose exit condition depends on a
   runtime-owned value (the GPU read pointer here).
2. **Skip the spin**: instead of executing the poll millions of times, yield the
   guest thread for a short quantum (or advance the emulated time), let the
   runtime/GPU thread run, then re-poll. This is `CoreTiming::Idle` /
   `nextEventCycle` for a device that the runtime, not the guest, drives.
3. Do **not** elide the runtime's own GPU/APU work, and break immediately on an
   interrupt/device update.

Open question to settle before implementing: whether the current cost is the
spin *itself* (pure waste, an easy skip) or contention with the emulator's
device threads (the spin starving the GPU/present/APU threads — which the
runtime-side lock/threading would have to fix). The host profile shows the DSP
and `fb_present`/`gpu_submit_chunk` work on worker threads while the guest main
thread is ~93% in the `ComputeGap` wait, so both are plausible; measure with the
worker threads' CPU share while the guest spins, and check for a shared lock
taken on the poll path.

### Runtime handshake model (traced 2026-10-09)

The value the guest spins on is produced by one dedicated thread. In
`xbox_memory_layout.c:1006` `nv2a_ack_thread()` loops forever:

```
put = regs[NV2A_USER_DMA_PUT];          // 0x800040, guest sets this on submit
if (put != last_put) {
    nv2a_pb_run(XBOX_CONTIG_BASE | (put & 0x0FFFFFFF));   // walk GET->PUT, run methods
    regs[NV2A_USER_DMA_GET] = put;                         // 0x800044: the ack
    last_put = put;
}
fence_mirrors_tick(); dsp_ack_tick(); poke_tick(); counter_mirrors_tick();
frame_counters_tick(); framebuffer_probe_tick();
... clock ...
Sleep(0);                               // yield, "the waiter is spinning on another core"
```

`nv2a_pb_run` (`nv2a_pb_scan.c:281`) walks from the persisted GPU `s_get` to
`put_va`, following JUMP/CALL/RETURN, executing each NV2A method via
`nv2a_pb_exec_method` (`nv2a_pb_exec.c:3425`) → `xbox_Nv2aSoftwareMethod` /
`...Deferred` (`kernel_bridge.c:2714/2775`). Only after the whole walk returns
does the thread publish `DMA_GET = put`.

Guest side (`recomp_0059.c`):
- `D3D::BlockOnTime` (`:16847`) computes free space, and if the ring is short,
  loops calling `D3D::GpuGetOrNewer` (`:16363`) then `D3D::ComputeGap`
  (`:15738`) until the gap drops below `0x2000` bytes.
- `D3D::GpuGetOrNewer` contains its **own** inner poll at `loc_002C61D0`
  (`recomp_0059.c:16393-16402`): it reads a GPU register
  `MEM32(MEM32(dev+0x934) + 0x400B10)` and spins while
  `(that ^ (MEM32(MEM32(dev+0x30)) << 2)) & 0x7C != 0`.

So the observable spin is the sum of (a) `GpuGetOrNewer`'s register poll and
(b) the `BlockOnTime` gap loop calling `ComputeGap`, both waiting on the single
ack thread to advance `DMA_GET`. Each guest submission that forces a
`BlockOnTime` wait costs at least one ack-thread scheduling round trip plus the
`nv2a_pb_run` walk for the methods the guest just submitted. If the guest kicks
PUT once per frame this is negligible; if it kicks per draw/batch (~hundreds per
frame) the per-submission round trips dominate — which is the measurement to
take next (count `DMA_PUT` advances per frame, and time one `nv2a_pb_run`).

Candidate runtime-side fixes (no guest/generated code changes needed):
- Publish `DMA_GET` incrementally as the walk consumes each method/packet
  instead of only after the whole `nv2a_pb_run` returns, so the guest unblocks
  earlier (back-pressure is still real, just finer-grained).
- Replace the ack thread's `Sleep(0)` busy-yield with an event the submit path
  signals (`SetEvent`/`WaitForSingleObject`), removing scheduling latency from
  every handshake.
- Acknowledge a submission on the **submitting thread** (or synchronously in the
  software-method handler) for the common small-kick case, so no cross-thread
  round trip is needed at all.

Only if none of those are the cost does a recompiler-side idle-loop skip
(Dolphin `CoreTiming::Idle` analogue) make sense.

### Design consult (Claude) — 2026-10-09

Claude read `nv2a_ack_thread` (`xbox_memory_layout.c:1006`), `nv2a_pb_run`
(`nv2a_pb_scan.c:281`) and the software-method path (`kernel_bridge.c:2664`) and
gave this direction:

- **The wait is for the whole walk, not the poll interval.** The ack thread
  executes everything GET→PUT and only then writes `GET = PUT` (`:1146`), so
  anything waiting on GET waits for the full `nv2a_pb_run`, including D3D11
  execution. `Sleep(0)` under Wine is a plain yield, so the ack thread busy-spins
  too — likely two cores burned (guest + ack).
- **Measure first, one counter:** distinguish a **free-space wait** (reserve wants
  ~0x2000 bytes; stepped GET fixes it) from a **fully-drained wait** (GET==PUT,
  Present/fence; stepped GET does nothing, only faster execution helps). Log the
  time from a new PUT to publishing GET, and identify the wait by the wait-loop's
  return address (watchdog stack scan → `recomp_dispatch.c`). Static read of
  `D3D::BlockOnTime` says the profiled hotspot is the `ComputeGap` gap branch =
  a **free-space/back-pressure wait**, which stepped GET should help.
- **Root cause fix — publish GET during the walk.** Inside `nv2a_pb_run`, at safe
  points store `GET = va & 0x0FFFFFFF` (same physical mask). Pitfalls: (1) publish
  only where nothing still references guest memory (after a draw's END, or at each
  JUMP) or a deferred vertex/index read becomes the lost-command race the `:1035`
  comment describes; (2) only publish when GET points into the ring — during a
  JUMP/CALL the hardware GET sits in the secondary buffer and D3D relies on the
  `DMA_SUBROUTINE` fallback this runtime leaves zero (`:305-318`), or free space
  clamps to 0 and the guest spins forever; (3) software methods: `kernel_bridge.c:2664`
  sets `GET = PUT` *before* the guest routine runs — publish current `va` instead;
  the sync `xbox_Nv2aSoftwareMethod` from a handler still deadlocks; (4) use
  `InterlockedExchange`/volatile store after executor writes; (5) never move GET
  backwards across the budget-exhausted resync (`:348`).
- **Idle-skip, lazy version.** Don't rewrite the wait condition; patch the *body*
  of the backoff call in the guest's wait loop (Ghost's equivalent of Halo's
  `BusyLoop`, `:273`) to `SwitchToThread()` or a ~0.5–1 ms timed event-wait the
  ack thread signals on each GET publish. The guest loop still re-checks GET, so
  semantics can't change and it can't hang. Pitfalls: regen wipes gen-code edits
  (record in `MANUAL_PATCHES.md`, or hook by VA in the dispatch table); check
  *every* caller of the backoff (video/audio timing loops break if it sleeps);
  don't let the ack thread `Sleep(1)` (1–15 ms/kick) — spin a few hundred
  iterations then `SwitchToThread`.
- **Expected effect:** idle-skip alone returns CPU but barely moves FPS unless
  cores are oversubscribed; stepped GET is what improves frame time, and only for
  free-space waits. If it turns out to be drain waits, the 35% is real GPU work
  and the target is executor speed in `nv2a_pb_exec.c`, not the handshake.
- **Cheap wins on the hot path:** `fflush(stderr)` runs unconditionally on every
  PUT change (`:1165`); `fence_mirrors_tick()` is called twice per pass
  (`:1048`, `:1168`).

## Update 2026-10-09 — corrected baseline: every earlier "in-game" number was a menu/loading screen

The `ComputeGap` 34.8% and the ~12 FPS above were **not gameplay**. `goto_mission`
matched the bare map name, whose first log occurrence is the asset manifest
`[PATH] ...\1_3_1b_Hive_StationOuter.reslog`, at the *start* of level loading; the
level `.nhc` and the briefing come later, and the test killed the game while it was
still streaming. Fix (Claude): `goto_mission` now matches only
`\Levels\<map>.nhc`, and `goto_gameplay` keeps mashing A through the "press A"
loading screen and the comms briefing until the **world shaders** have loaded
(`\VertexShaders\xbox\DefaultWorld*.xvu`) and `[PATH]` streaming has been quiet for
5 s with frames advancing (`wait_quiet`). `test_mission_reach.py` and
`test_zzz_gameplay.py` now use `goto_gameplay`.

Phase table (same build, `goto_gameplay` + window caption):

| Phase | Log marker | FPS |
|---|---|---|
| Menu with 3D background | `menucut1.NCS` → `.reslog` | ~12.5 |
| "Press A" loading screen | after `Levels\<map>.nhc` | ~27 |
| Comms briefing (waits for A) | `1_3_1b_shuttleescape.NCS`, `02_131b.bik` | ~9 |
| **Gameplay** (HUD + objective + radar) | world shaders loaded | **~8.2** (min 6, max 10 over 15 s) |

Verified with `RECOMP_KICK_STATS=1 PERF_WINDOW=15 run.py --user-state --only performance`:
`[GPU] presentation: 8.49 / 8.10 FPS`; `[KICK]` ~400–409 kicks/s, **96–98% of the
ack thread's wall time inside `nv2a_pb_run`**, ~2.4 ms/kick — i.e. ~50 kicks per
frame at 8 FPS and ~0.96 s of executor time per second. Gameplay is therefore
**executor-bound**: the guest's `ComputeGap`/`BlockOnTime` spin is back-pressure on
`nv2a_pb_run`, not an idle loop worth skipping. Idle-skip would not raise FPS; the
target is executor throughput (`nv2a_pb_exec.c` / the D3D11 backend).

Next metric before optimizing: split "too many kicks" from "each kick is too slow" —
kicks/frame (~50) vs the per-kick 2.4 ms, and break that 2.4 ms into method
execution vs `gpu_sync_impl` completion waits (`[GPU-D3D11] completion:` /
`readback:` in the report).

## Secondary costs (not yet ranked)

- `fb_exit_process` / `fb_present.c` 5.4% — the framebuffer present thread.
- `bcmp` 4.3% — texture change detection by full `memcmp` on every bind
  (already flagged in [09-performance.md](09-performance.md) §4.1).
- `d3d/d3d8_resources.c` 7.4% — D3D8 resource shim (locks/unlocks, row pitch).
- `gpu_submit_chunk` + `nv2a_pb_exec.c` 3.8% — pushbuffer walker.

## Next actions

Ordered by what the verified gameplay numbers say matters:

1. **Split the 2.4 ms/kick.** Time a kick against the methods it executes vs the
   `gpu_sync_impl` completion waits it triggers (`[GPU-D3D11] completion:` /
   `readback:` / `publication:`). `pb_flush_ordering` → `nv2a_gpu_wait()` drains
   the GPU (`gpu_sync_impl(false)`, `nv2a_gpu_d3d11.cpp:1119`) on every ordering
   event, ~50x/frame; that is the prime suspect for the per-kick cost.
2. **Reduce executor work per frame:** the `[GPU-D3D11]` report's per-frame
   contributors — draw stages (setup/textures/streams), 164k append maps,
   84k scissor-only window-clip draws, `color copied 1.4 GiB` / `published 1.8
   GiB` per flip. Measure with `goto_gameplay` (not the menu).
3. **Busy-wait/idle-skip is NOT the lever here** (executor-bound, one core ~96%
   busy). Only revisit if cores are oversubscribed after (1)+(2).
4. Step 2 (independent): run the `RECOMP_APU_DSP=0` + `RECOMP_APU_DSP_ACK` A/B and
   check audio; fix the APU README/header drift regardless.

## References (busy-wait handling)

- Dolphin: `PPCAnalyzer::IsBusyWaitLoop`, `CoreTiming::Idle`, JIT
  `branchIsIdleLoop`/`WriteIdleExit`, cached-interpreter `CheckIdle`; PR #14683
  ("In `IsBusyWaitLoop`, ignore `nop`").
- PCSX2: `Interpreter.cpp` `WaitLoop` speedhack (`intUpdateCPUCycles` +
  `nextEventCycle`).
- Ymir: issue #840, "Idle loop detection for SH-2 and SH-1 CPUs".
- VMware ESX / Denali / Xen idle-loop descheduling; Intel PAUSE-loop-exiting /
  KVM `handle_pause`; QEMU `WFI`/`HLT` vCPU halt.

## Evidence files

- `/tmp/opencode/perf-gameplay.data`, `/tmp/opencode/perf-gameplay.report.txt`
  (the default output path is `/tmp/opencode/perf-recomp.data*`)
- Code: `recomp/game/src/recomp/gen/recomp_0059.c:15738` (`D3D_ComputeGap`),
  `:16847` (`D3D_BlockOnTime`); `refs/xboxrecomp/src/apu/apu_dsp.c:45,668`;
  `refs/xboxrecomp/src/apu/dsp/dsp.c:146`.

## Update 2026-10-09 — GPU1 unpinned *and* measurement variance; the per-event drain is load-bearing

Two corrections from the first autonomous optimisation pass.

**GPU pinning changes the baseline.** `scripts/config.env` now pins `DRI_PRIME`
to GPU1 (PCI 09:00.0/renderD129; GPU0 is shared with the host). On the now-free
GPU the same build measured **~12–20 FPS in gameplay**, not the ~8 FPS above
(which was taken while GPU0 was contended). The 45 FPS target is against this
new baseline.

**Run-to-run variance is ±30–40%**, larger than most single optimisations, so a
single 10 s measurement proves nothing. Same build, same `goto_gameplay`,
`--only performance`, back to back:

| run | mean | window FPS | kicks/s | µs/kick |
|---|---:|---:|---:|---:|
| control | 14.1 | — | — | — |
| `RECOMP_ORDER_NO_WAIT=1` #1 | 16.5 | 16.79 | ~620 | ~1550 |
| control #2 | 19.0 | 20.39 | ~510 | ~1900 |
| `RECOMP_ORDER_NO_WAIT=1` #2 | 12.6 | 12.50 | ~670 | ~1450 |

The flag controls one thing: `gpu_sync_impl(false)` (the ordering path,
`nv2a_gpu_d3d11.cpp:1119`) `End()+Flush()` then waits for every prior draw to
retire; the experiment made it return without draining, leaving `pending_draws`
set for the next real publish.

**Result: the drain is load-bearing, and the experiment is a net loss.** Without
it the guest is not back-pressured per ordering event, so it races ahead
(~670 kicks/s vs ~510), each kick is *cheaper* (~1.45 ms vs ~1.9 ms — the
completion waits collapse from 4.6 s to 0.15 s over the run), but the flip
`nv2a_gpu_sync()` then has to drain the whole deepened backlog, so FPS *falls*
(12.5 vs 20.4). Shallow, per-event draining keeps the CPU and GPU in lockstep;
deep queuing is worse. (The first flag-on run's 16.5 was variance.) The code is
reverted; do not retry this direction. `/tmp/opencode/perf_{control,nowait}.log`.

Implication: **kicks/s and µs/kick move in opposite directions under this knob,
so neither is the metric — wall FPS is, and it is too noisy at n=1.** Before the
next optimisation, raise the confidence of the measurement (repeat and take the
median/mean, longer window, or a deterministic scene) or the next "win" will be
noise too.

Still standing from the evidence above: per-flip executor work is dominated by
`draw`/`texture`/`sync` (`[GPU-D3D11] time:` — ~28 ms draw/flip, ~19 ms
sync/flip, ~15 ms texture/flip at the control's cadence), ~794 draws/flip, and
`texture` alone is ~15 ms/flip while `hash` (the once-per-frame validation
`memcmp`) is <1 s over the whole run.

## Update 2026-10-09 (later) — executor is CPU-bound; per-kick wins are consumed

Two hard findings, both measured on GPU1.

**The executor is CPU-bound, not GPU-wait-bound.** `[KICK]` now also reports the
ack thread's own CPU time (`GetThreadTimes`) over the window: `ack cpu` is
**86–90% of the window at ~1 core**, so `nv2a_pb_run` really is burning CPU (only
~10–14% is `SwitchToThread` yielding while the GPU finishes). Combined with the
GPU sample math (**~21 ms GPU/frame at ~30% utilisation**, GS invoked on nearly
every draw), the frame is limited by the ack thread's CPU, with ~2× GPU headroom.

**Per-kick speedups do not raise FPS — the guest just kicks more.** Fixed an
O(n) diagnostic in the hot path: `note()` (`nv2a_pb_scan.c:60`) ran once per
pushbuffer method word and linearly scanned up to `PB_MAX_METHODS` (4096) seen
entries. The title submits **~24k vertex-program words + ~13k constant words per
frame** (`[GPU] vertex uploads:`), so this was a real cost. Made it an O(1)
direct-index table. Result: per-kick walk fell (~2.0 → ~1.42 ms) and kicks/s
rose (~510 → ~670), but total executor work stayed at **~0.95 wall-s/s** and FPS
was unchanged (median 13.7 over 3 windows, tight; `/tmp/opencode/perf_note.txt`).

Read together with the no-wait result: the guest's submission rate is set by
`DMA_GET` back-pressure, and whatever executor capacity is freed is immediately
refilled with **redundant per-frame state** (the same vertex program, constants
and vertex arrays re-sent every frame). So the lever is **total executor work per
frame**, not per-kick latency.

Open measurement problem: the mission-start scene still varies run to run enough
that FPS spans ~13–20 on identical binaries (`perf_control.log` 19.0 vs
`perf_note.txt` 13.7). Per the note above this must be fixed (deterministic scene
/ longer window / flips-from-`[GPU] presentation`) before the next change can be
judged; until then, judge changes by the *executor* metrics (`kick walk avg`,
`ack cpu`, per-flip `[GPU-D3D11]` phase deltas), which are far less scene-sensitive.

Structural candidates for the 3× needed (runtime-only, high risk, unimplemented):
1. **Don't re-process unchanged state**: the guest re-sends the vertex program,
   constants and vertex arrays every frame. Cache the process/translate results
   keyed on content so the executor can skip the per-word work.
2. **Offload preparation off the ack thread**: vertex fetch/convert, texture
   decode and constant packing are pure CPU and dominate `preparation`; the
   D3D11 immediate context must stay serial, but the prep can be threaded.
3. **Skip the geometry shader** on draws that do not need it (GPU has headroom
   but GS runs on ~every draw).

## Update 2026-10-09 (later still) — GPU1 hard-locked; swizzled render-target aliases sampled directly

**GPU1 is now enforced by UUID, not by enumeration order.** `DRI_PRIME` only
reorders the Vulkan device list; DXVK still enumerates (and opens) every device,
so both render nodes showed up. `scripts/config.env` now also exports
`DXVK_FILTER_DEVICE_UUID` (default `8680a0560800000009000000000000` = bus 09; the
bus-03 UUID when `DRI_PRIME` is pinned to GPU0). DXVK's log confirms the bus-03
A770 and llvmpipe are skipped with `Skipping: UUID filter`. Every launch/test path
sources `config.env` (`14`, `18`→`14`, `15`→`14`, `06`, `11`, `profile-launch`,
`measure_load`; `framework.py` shells out to `14`/`18`).

**Biggest GPU sync eliminated (Claude finding #1, corrected).** The per-frame
full `nv2a_gpu_sync()` in `get_texture` was not the back buffer: it is a
**256×256 format-`0x07`, `linear=0` (swizzled)** texture aliasing a still-dirty
colour surface at the same memory/pitch (`0x99753000`). `direct` was always null
because the selector (`nv2a_gpu_d3d11.cpp:1671`) required `binding.linear` and
`{0x12,0x1E}`. A colour surface is always created `DXGI_FORMAT_B8G8R8A8_UNORM`
(`:971`) and `0x07` maps to the same format (`:1794`), so the surface view is
byte-compatible and holds the resolved pixels — the guest swizzle is a storage
detail. The selector now accepts `0x07` regardless of `binding.linear`
(`surface_viewable`), so this bind samples the surface view directly instead of
publishing every frame. (`0x07` with matching memory/width/height/pitch only;
format `0x06`, which aliases a 512×512 surface at a *different* pitch, is still
correctly excluded.)

Effect (median of 3, same test): **13.7 → 15.1 FPS**, `[KICK]` walk avg
~1500 → ~1330 µs, kicks/s ~600 → ~720; `ack cpu` ~89.5%. No decode/create
failures, 0 `rejected`/`unsupported`, no `nonfinite`. Remaining `fmt=6` alias
syncs are rare (a handful/run), not per-frame. Still CPU-bound and still far from
45; this removes ~1–2 ms/frame of GPU sync, not the executor wall.