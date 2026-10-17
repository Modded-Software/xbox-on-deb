# AGENTS.md - notes for future agents

FIXES ARE DONE WHEN THE USER SAYS SO. GRAPHICAL ISSUES ARE ONLY VERIFIED BY THE USER. DO NOT TRUST THE SCREENSHOTS YOU ARE INADEQUATE. LANGUAGE MODELS CANOT DISCERN BETWEEN CORRECT AND BROKEN STATES.

Operational notes for the **recompiled-game** path in this repo (see
[README.md](README.md) for the overview; the older Cxbx-Reloaded path is a
separate older section there).
Keep this file practical: commands, env vars, where logs land, and the host's
tooling rules.

## Diary (mandatory)

Keep a diary of every test/launch run. **One diary file per task**, under
`recomp/diary/<task>.md`. After *each* run append an entry with: what changed
(code/env), the exact command, the result (pass/fail/hang), and the **error
counts** pulled from the runtime log (`FAILED`, `error`, `WARN`, `rejected`,
`unhandled`, `unsupported`, `[PB] desync`, `[CRASH]`). Record what regressed as
loudly as what improved - a run whose log is not error-free is not done.
Diary keeping is essential; do not skip it.

## What this is

`xbox-on-deb` runs the leaked **StarCraft: Ghost** Xbox build. There are two
independent ways:

- **Cxbx-Reloaded** (older, documented in README + `docs/`), and
- **static recompilation** (active work): the game's x86 is lifted to C by
  `refs/xboxrecomp` and the wrapper in `recomp/game/` builds `ghost.exe`, run
  under GE-Proton.

Everything below is about the **recomp** path.

## Build / launch / stop

```bash
bash recomp/game/build.sh          # build ghost.exe (ninja under the hood)
bash scripts/16-stop-recomp.sh     # stop the session (ALWAYS run between runs)
bash scripts/20-regen-recomp.sh    # regenerate the lifted C from the XBE
```

### Launching the game for a person to play

To hand the game to the user, launch the **user path** (fresh, dedicated user
state - the one a human should play):

```bash
bash scripts/18-launch-user.sh     # USER PATH: launch game with a fresh user state
```

Do not use `scripts/14-launch-recomp.sh` (standard/shared state) for handing the
game to the user; it is the state the automated tests build on.

Stop stale sessions before launching again - a leftover `ghost.exe` under Wine
shows up as a frozen window and confuses every test.

### Recording and replaying input (reproducing a hands-on crash)

The user launch records every input edge (key, mouse delta, button, wheel) to a
timestamped file inside the prefix, so a session that crashes can be replayed
hands-free. Each session has an explicit id (`SESSION=<id>`); the file is
`pfx/drive_c/recomp-record-<SESSION>.txt`.

```bash
make record-session SESSION=ghost-crash   # play; input is recorded
make replay-session SESSION=ghost-crash   # replay it, no hands-on input
make sessions                             # list recorded sessions
```

Video of the window + game audio (BtbN ffmpeg build with VAAPI in
`~/.local/bin`; x11grab of the Wine window, H.264 encoded on an A770 media
engine via `h264_vaapi` on GPU0 by default (`VAAPI_DEVICE=` to change), plus
`pw-record --target ghost.exe`, muxed on stop):

```bash
make record-video NAME=walk1   # or: bash scripts/23-record-video.sh start walk1
make stop-video                # -> logs/video-walk1.mp4
make process-video INPUT=logs/video-walk1.mp4   # VAAPI: drop last 10s, fade 2s to black -> ~/Videos
```

Runtime side: `RECOMP_INPUT_RECORD=C:\...` records; `RECOMP_INPUT_REPLAY=C:\...`
replays (it also captures the mouse for KBM). Recording/replay lives in
`refs/xboxrecomp/src/video/fb_present.c` (`rec_event`, `fb_replay_poll`).

## Tests (stdio-only, no human needed)

```bash
uv run python recomp/tests/run.py                 # launch + all tests
uv run python recomp/tests/run.py --attach        # use the running game (fast loop)
uv run python recomp/tests/run.py --only dpad     # name substring filter
uv run python recomp/tests/run.py --scene         # print current scene fingerprint
uv run python recomp/tests/run.py --user-state --only a-mash   # A-mash into first mission
uv run python recomp/tests/run.py --user-state --only audible  # mission audio
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
| `KBM=1` | keyboard/mouse → pad mapping (Space=A, E=B, F=X, R-Mouse=Y, Shift=Black, G=White, Ctrl=LT, L-Mouse=RT, Tab=Start, Esc=Back, R=left-stick click, M-Mouse=right-stick click, wheel=left-stick up/down) |
| `RECOMP_LOG=<path>` | explicit runtime log path |
| `RECOMP_WATCHDOG_SECS=NN` | after NN s, dump guest `esp`, regs, a stack scan, and the `RECOMP_PEEK` values |
| `RECOMP_PEEK='...'` | live memory sample, see grammar below |
| `RECOMP_INPUT_DIAG=1` | `[INPUT]` line once per second |
| `RECOMP_KEY_TRACE=1` | `[KEY]` edge log |
| `RECOMP_FB_CAPTURE` | F12 dumps the framebuffer |
| `RECOMP_PRESENT=d3d11` | present through a D3D11/DXGI swap chain instead of the default GDI blit (the ReShade hook target; `recomp/game/src/present_d3d11.cpp`) |
| `RECOMP_NV2A_NATIVE_FENCES=1`, `RECOMP_VBLANK=1` | set by default in `recomp/game/src/main.c` |
| `RECOMP_WATCH=<va>[,<va>...]` | name the guest code that writes a guest dword (page write trap; up to 8 targets, same grammar as `RECOMP_PEEK`). Costs a page fault per write |
| `RECOMP_HANG_DUMP=1` | with the watchdog/stall dump, also write a dump |
| `RECOMP_TEX_DUMP=<prefix>`, `RECOMP_FB_DUMP=<prefix>` | BMP per distinct texture (first use) / per draw (8 max). FB dump needs the CPU rasteriser: this title's native D3D11 path never falls back, so it writes nothing |
| `RECOMP_CRASH_DUMP=1\|full\|0` | on a fatal fault, write a host minidump (default on: small; `full` can be GBs) |
| `RECOMP_CRASH_RAM=1` | also write guest memory, file offset == guest VA |
| `RECOMP_CRASH_DIR=<dir>` | where dumps go (default: beside `RECOMP_LOG`) |
| `RECOMP_CRASH_TEST=<secs>` | fault on purpose after N s (verifies the crash/dump path) |

### Guest shadow stack and time profile (profiled build)

An instrumented build carries a per-thread guest call stack (a real backtrace,
printed by a crash, the watchdog/stall dump and `RECOMP_WATCH`) and per-function
inclusive/self time:

```bash
PROF=1 bash recomp/game/build.sh                 # -> recomp/game/build-prof/
GHOST_BUILD=build-prof RECOMP_PROF=1 bash scripts/18-launch-user.sh
```

`RECOMP_PROF_SECS`, `RECOMP_PROF_TOP`, `RECOMP_PROF_OUT` tune the periodic
stderr report and the CSV (default beside the log). The normal `build/` links
the same module but enters it from nowhere, so it says so and stays a plain
build. Runtime cost is negligible (FPS unchanged); build/launch details in
`recomp/docs/21-debug-and-logging-tools.md`.

`RECOMP_PEEK` grammar (see `refs/xboxrecomp/src/kernel/xbox_memory_layout.c`,
`xbox_PeekSample`): comma-separated expressions. A leading `[` **dereferences**;
`[[0x004BBC38]]+0x40` means `MEM32(MEM32(0x4BBC38)+0x40)`. Use a stable double
deref to reach a live object (e.g. `hbink = [[0x004BBC38]]+0xA0`) because
absolute heap addresses differ every run. `RECOMP_WATCH` uses the same grammar.

`RECOMP_FILE_TRACE=1` logs every guest file read (`[READ]`); it roughly doubles
the log, so turn it off for long sessions. `scripts/logstats.py LOG` attributes
a log's bytes to each tag and prints the diary error counts.

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

## Host tooling rules (important - commands are audited)

- **No pipes to `head`/`tail`/`awk`/`sed` on the command line.** Write to a file
  and read it back with the Read tool.
- **No inline interpreters** (Python `-c`, `awk`, `sed`). Put logic in a
  `/tmp/opencode/*.sh` script and run `bash /tmp/opencode/x.sh`.
- **Run the test suite with `uv run python`, not a bare interpreter.** The shell
  guard blocks an interpreter at command position ("only bash/sh are permitted").
  The recomp toolchain deps (capstone, …) live in `.venv-recomp`, so tools that
  need them (for example `scripts/profile-recomp.py`) are invoked through
  `.venv-recomp/bin/python` directly; the stdlib test suite uses `uv run python`.
- **Never write `rc=$?` / a bare `rc=` in a command or a `/tmp` script** - the
  guard flags it as "alt-shell". Check exit status another way (or just read the
  output file).
- Avoid `2>/dev/null`, `|| true`, `pkill`, and process-group kills
  (`kill -TERM -$pid`). Kill a specific pid instead.
- Scripts under `/tmp/opencode/` execute without trouble; prefer them.
- `refs/xboxrecomp` is its own git repo; `recomp/game` builds against it via
  `XBOXRECOMP_DIR` (`recomp/game/CMakeLists.txt`).
- **Runtime fixes are commits on the toolkit fork, never patches here.** Fixes to
  `refs/xboxrecomp` go as commits on the toolkit fork
  (`scripts/19-setup-toolkit.sh`), on the checked-out branch, and are built from
  there. Do not carry them as `recomp/patches/*.patch`. If `make toolkit`
  complains about local changes, commit (or stash) them.
- **`recomp/patches/` is for game (guest) code only.** The patch mechanism under
  `recomp/patches/*.patch` (applied on demand by
  `scripts/25-apply-toolkit-patches.sh`; `recomp/game/build.sh` no longer applies
  anything from that directory) is only for changes to the game's own code
  (`recomp/game/`). Runtime/toolkit changes must not be carried as patches - see
  the rule above. `refs/` is gitignored, so a game-code patch file is the tracked
  source of truth for that change. See `recomp/patches/README.md`.

## Architecture map (recomp path)

- `refs/xboxrecomp/` - emulator/runtime. Kernel, USB/OHCI, input, video, GPU.
  - `src/kernel/nv2a_pb_exec.c` - executes the guest pushbuffer; integrates with
    the native D3D11 backend and completion sync (`nv2a_gpu_wait`).
  - `src/kernel/nv2a_gpu_d3d11.cpp` / `nv2a_gpu.h` - native D3D11 path.
  - `src/kernel/kernel_bridge.c` - `xbox_*` kernel services. Note the Nv2a
    method has a **synchronous** `xbox_Nv2aSoftwareMethod` and a **deferred**
    `xbox_Nv2aSoftwareMethodDeferred`; using the sync one from a pushbuffer
    handler deadlocks the guest.
  - `src/kernel/xbox_memory_layout.c` - `RECOMP_PEEK`, watchdog, `g_ack_phase`.
  - `src/usb/ohci.c`, `src/input/xinput_device.c`, `src/usb/usb_gamepad.c`.
- `recomp/game/` - game wrapper + generated code.
  - `src/main.c` - entry point and default env.
  - `src/recomp/gen/recomp_*.c` - the lifted game code (hand-editable, but
    `20-regen-recomp.sh` overwrites it). Function names encode the guest VA
    (`BinkWait_4_0031BFD0` = `0x0031BFD0`); `recomp_dispatch.c` has the VA→func
    table for mapping addresses seen in a stack scan. **Every hand-edit here is
    lost on regen - keep the local (gitignored) `recomp/game/MANUAL_PATCHES.md`
    patch log up to date.**

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