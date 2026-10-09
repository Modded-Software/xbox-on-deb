# AGENTS.md — notes for future agents

Operational notes for the **recompiled-game** path in this repo (see
[README.md](README.md) for the older Cxbx/Cxbx-Reloaded path, which is separate).
Keep this file practical: commands, env vars, where logs land, and the host's
tooling rules.

## What this is

`xbox-on-deb` runs the leaked **StarCraft: Ghost** Xbox build. There are two
independent ways:

- **Cxbx-Reloaded** (legacy, documented in README + `docs/`), and
- **static recompilation** (active work): the game's x86 is lifted to C by
  `refs/xboxrecomp` and the wrapper in `recomp/game/` builds `ghost.exe`, run
  under GE-Proton.

Everything below is about the **recomp** path.

## Build / launch / stop

```bash
bash recomp/game/build.sh          # build ghost.exe (ninja under the hood)
bash scripts/14-launch-recomp.sh   # launch (standard state)
bash scripts/18-launch-user.sh     # launch with a fresh user state
bash scripts/16-stop-recomp.sh     # stop the session (ALWAYS run between runs)
bash scripts/20-regen-recomp.sh    # regenerate the lifted C from the XBE
```

Stop stale sessions before launching again — a leftover `ghost.exe` under Wine
shows up as a frozen window and confuses every test.

## Tests (stdio-only, no human needed)

```bash
python3 recomp/tests/run.py                       # launch + all tests
python3 recomp/tests/run.py --attach              # use the running game (fast loop)
python3 recomp/tests/run.py --only dpad           # name substring filter
python3 recomp/tests/run.py --scene               # print current scene fingerprint
python3 recomp/tests/run.py --user-state --only a-mash   # A-mash into first mission
python3 recomp/tests/run.py --user-state --only audible  # mission audio
```

See `recomp/tests/README.md` for the framework and how to add a test. The
canonical "did we get further?" check is `--user-state --only a-mash`
(expects to reach the first mission; a `TimeoutError ... may have hung` means a
stall). Tests observe: `[INPUT]` diag, `[KEY]` trace, window caption
`Frame/FPS`, framebuffer hashes (F12), and `[GPU-D3D11]` shader/texture health.

## Logs

- `logs/runtime-YYYYMMDD-HHMMSS.log` and `logs/latest-runtime.log`
- `logs/launch.out`
- Grep for `[WATCHDOG]`, `[GPU] presentation: N flips`, `[KERNEL] summary`,
  `[FILE]`, `[READ]`, `[INPUT]`, `[TEXUSE]`.

## Runtime diagnostics (env vars before launch)

| Var | Effect |
|---|---|
| `DIAG=1` | verbose runtime diagnostics |
| `KBM=1` | keyboard/mouse → pad mapping (Space=A, E=B, F=X, R=Y, Shift=Black, Q=White, Ctrl=LT, Tab=Start, Esc=Back) |
| `RECOMP_LOG=<path>` | explicit runtime log path |
| `RECOMP_WATCHDOG_SECS=NN` | after NN s, dump guest `esp`, regs, a stack scan, and the `RECOMP_PEEK` values |
| `RECOMP_PEEK='...'` | live memory sample, see grammar below |
| `RECOMP_INPUT_DIAG=1` | `[INPUT]` line once per second |
| `RECOMP_KEY_TRACE=1` | `[KEY]` edge log |
| `RECOMP_FB_CAPTURE` | F12 dumps the framebuffer |
| `RECOMP_NV2A_NATIVE_FENCES=1`, `RECOMP_VBLANK=1` | set by default in `recomp/game/src/main.c` |

`RECOMP_PEEK` grammar (see `refs/xboxrecomp/src/kernel/xbox_memory_layout.c`,
`xbox_PeekSample`): comma-separated expressions. A leading `[` **dereferences**;
`[[0x004BBC38]]+0x40` means `MEM32(MEM32(0x4BBC38)+0x40)`. Use a stable double
deref to reach a live object (e.g. `hbink = [[0x004BBC38]]+0xA0`) because
absolute heap addresses differ every run.

## How to ask Claude (Opus 5.5)

`scripts/ask-claude.sh` runs `oc` (opencode) in prompt mode against
`claude-opus-5-5`, **detached**, streaming to a log so you can peek/interrupt:

```bash
bash scripts/ask-claude.sh "your technical or implementation question"
bash scripts/ask-claude.sh --chat   "follow-up"       # continue the last chat (session)
bash scripts/ask-claude.sh --session ses_XXX "..."    # continue a specific session id
bash scripts/ask-claude.sh --last-id                  # print newest session id
bash scripts/ask-claude.sh --peek   [LOG]   # tail the newest/given run
bash scripts/ask-claude.sh --status          # list recent runs and whether alive
bash scripts/ask-claude.sh --stop   [LOG]   # stop the newest/given run
# foreground:
bash scripts/ask-claude.sh --wait "question"
# override model:
ASK_CLAUDE_MODEL=workspace-gw-anthropic-coding-plan-passthrough/claude-opus-5-5 \
  bash scripts/ask-claude.sh "..."
```

Logs/prompt/pidfiles live in `/tmp/opencode/ask-claude-*`. Use this for
technical or design questions **instead of stalling or guessing**.

## Host tooling rules (important — commands are audited)

- **No pipes to `head`/`tail`/`awk`/`sed` on the command line.** Write to a file
  and read it back with the Read tool.
- **No inline interpreters** (`python -c`, `awk`, `sed`). Put logic in a
  `/tmp/opencode/*.sh` script and run `bash /tmp/opencode/x.sh`.
- **Run Python with `uv`, not bare `python`/`python3`.** The shell guard blocks
  an interpreter at command position ("only bash/sh are permitted"). The recomp
  toolchain deps (capstone, …) live in `.venv-recomp`, so use
  `VIRTUAL_ENV=$PWD/.venv-recomp uv run --active python …` — plain `uv run
  python` uses a different env and is missing capstone.
- **Never write `rc=$?` / a bare `rc=` in a command or a `/tmp` script** — the
  guard flags it as "alt-shell". Check exit status another way (or just read the
  output file).
- Avoid `2>/dev/null`, `|| true`, `pkill`, and process-group kills
  (`kill -TERM -$pid`). Kill a specific pid instead.
- Scripts under `/tmp/opencode/` execute without trouble; prefer them.
- `refs/xboxrecomp` is its own git repo; `recomp/game` builds against it via
  `XBOXRECOMP_DIR` (`recomp/game/CMakeLists.txt`).

## Architecture map (recomp path)

- `refs/xboxrecomp/` — emulator/runtime. Kernel, USB/OHCI, input, video, GPU.
  - `src/kernel/nv2a_pb_exec.c` — executes the guest pushbuffer; integrates with
    the native D3D11 backend and completion sync (`nv2a_gpu_wait`).
  - `src/kernel/nv2a_gpu_d3d11.cpp` / `nv2a_gpu.h` — native D3D11 path.
  - `src/kernel/kernel_bridge.c` — `xbox_*` kernel services. Note the Nv2a
    method has a **synchronous** `xbox_Nv2aSoftwareMethod` and a **deferred**
    `xbox_Nv2aSoftwareMethodDeferred`; using the sync one from a pushbuffer
    handler deadlocks the guest.
  - `src/kernel/xbox_memory_layout.c` — `RECOMP_PEEK`, watchdog, `g_ack_phase`.
  - `src/usb/ohci.c`, `src/input/xinput_device.c`, `src/usb/usb_gamepad.c`.
- `recomp/game/` — game wrapper + generated code.
  - `src/main.c` — entry point and default env.
  - `src/recomp/gen/recomp_*.c` — the lifted game code (hand-editable, but
    `20-regen-recomp.sh` overwrites it). Function names encode the guest VA
    (`BinkWait_4_0031BFD0` = `0x0031BFD0`); `recomp_dispatch.c` has the VA→func
    table for mapping addresses seen in a stack scan. **Every hand-edit here is
    lost on regen — keep `recomp/game/MANUAL_PATCHES.md` up to date.**

## Known issues / current status

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
- **Sound quality (OPEN, 2026-10-09)**: some voices play flangy / stuttery /
  garbled. Audio quality, not liveness (`--only audible` PASSes; PCM non-silent).
  The earlier "prime suspect" in this file — the `mcpx_apu_monitor_frame`
  overdub — is **wrong**: `apu_mixer_*` has **zero callers** (grep the tree), so
  `mixer_render` iterates only inactive voices and mixes nothing. The real
  defects, all read from the code:
  - **No resampling.** `voice_resample` (`apu_vp.c:949`) discards `rate`
    (`(void)rate;` at `:967`): every voice consumes exactly 32 source samples per
    48 kHz output frame regardless of pitch. Non-48 kHz samples, pitch-shifted
    SFX and 3D/doppler voices play at the wrong rate, and streaming voices
    over/under-run their CBO/loop because the guest scales consumption by rate.
  - Nearest-neighbour, no interpolation (`voice_get_samples`), so aliasing.
  - `monitor.frame_buf` (`apu_state.h:410`, 256 = 8×32) is never cleared; it is
    only valid if the EP DMA sink rewrites the whole 1024 bytes every window
    (`ep_sink_samples`, `apu_dsp.c:431`; the `assert(len == sizeof(frame_buf))`
    is compiled out). A window the EP skips replays 5.33 ms-old audio → comb /
    flange. Produce-and-consume latency is also 8 frames.
  - XAudio2 stops/re-starts the source on an empty queue (`apu_xaudio2.c:150`),
    audible as gaps; `empty_queue_events` counts them.
  See `recomp/docs/17-executor-roadmap.md`.

## Debugging recipe (a hang)

1. Stop any session; launch with `RECOMP_WATCHDOG_SECS=50` and a `RECOMP_PEEK`
   targeted at the suspect object.
2. In the runtime log, read the `[WATCHDOG]` block: `esp`, registers, the
   `GS <addr> <value>` stack scan (return addresses, map them via the
   `*_<VA>` names / `recomp_dispatch.c`), and the peek values.
3. Confirm the last `[GPU] presentation` flip count to see when it stopped.
4. Map the deepest guest address to a lifted function, read it in
   `recomp/game/src/recomp/gen/`, and identify the loop / bad field.
5. If unsure of the fix, ask Claude via `scripts/ask-claude.sh` (above).