# AGENTS.md — notes for future agents

FIXES ARE DONE WHEN THE USER SAYS SO. GRAPHICAL ISSUES ARE ONLY VERIFIED BY THE USER. DO NOT TRUST THE SCREENSHOTS YOU ARE INADEQUATE. LANGUAGE MODELS CANOT DISCERN BETWEEN CORRECT AND BROKEN STATES.

Operational notes for the **recompiled-game** path in this repo (see
[README.md](README.md) for the older Cxbx/Cxbx-Reloaded path, which is separate).
Keep this file practical: commands, env vars, where logs land, and the host's
tooling rules.

## Diary (mandatory)

Keep a diary of every test/launch run. **One diary file per task**, under
`recomp/diary/<task>.md`. After *each* run append an entry with: what changed
(code/env), the exact command, the result (pass/fail/hang), and the **error
counts** pulled from the runtime log (`FAILED`, `error`, `WARN`, `rejected`,
`unhandled`, `unsupported`, `[PB] desync`, `[CRASH]`). Record what regressed as
loudly as what improved — a run whose log is not error-free is not done.
Diary keeping is essential; do not skip it.

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
bash scripts/16-stop-recomp.sh     # stop the session (ALWAYS run between runs)
bash scripts/20-regen-recomp.sh    # regenerate the lifted C from the XBE
```

### Launching the game for a person to play

To hand the game to the user, launch the **user path** (fresh, dedicated user
state — the one a human should play):

```bash
bash scripts/18-launch-user.sh     # USER PATH: launch game with a fresh user state
```

Do not use `scripts/14-launch-recomp.sh` (standard/shared state) for handing the
game to the user; it is the state the automated tests build on.

Stop stale sessions before launching again — a leftover `ghost.exe` under Wine
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

Runtime side: `RECOMP_INPUT_RECORD=C:\...` records; `RECOMP_INPUT_REPLAY=C:\...`
replays (it also captures the mouse for KBM). Recording/replay lives in
`refs/xboxrecomp/src/video/fb_present.c` (`rec_event`, `fb_replay_poll`).

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
| `KBM=1` | keyboard/mouse → pad mapping (Space=A, E=B, F=X, R-Mouse=Y, Shift=Black, G=White, Ctrl=LT, L-Mouse=RT, Tab=Start, Esc=Back, R=left-stick click, M-Mouse=right-stick click, wheel=left-stick up/down) |
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