# xbox-on-deb

**xbox-on-deb** collects the tooling, runtime work, and research for running original Xbox games natively, with no CPU emulator at run time: each game's XBE is statically recompiled to C and cross-built as a Windows x64 executable (`ghost.exe`). The primary, tested target is Debian and Ubuntu, where that executable runs under GE-Proton on a Vulkan GPU; because the build output is an ordinary Windows x64 program, Windows itself is a target platform too.

StarCraft: Ghost (the leaked May 2004 Xbox build) is the first game shipped this way. It boots, reaches the menus, and plays missions with audio, controller, and keyboard-and-mouse input.

> No game data is included here. See [Legal](#legal).

## Getting Started

### Prerequisites

- Ubuntu 24.04 or Debian with an X11 or XWayland session and a Mesa Vulkan driver (developed on Intel Arc A770, ANV). This is where everything is built and tested; the recompiled output is Windows x64 and runs on Windows with the D3D11 runtime, but Windows is not exercised here.
- GE-Proton in `~/.steam/root/compatibilitytools.d/`. The [windows-on-deb](../windows-on-deb/README.md) scripts `01` to `03` install it with Steam and the system packages.
- `cmake`, `git`, and `uv`. The cross-compiler is zig from the `ziglang` PyPI package, configured by `recomp/toolchain/zig-windows-x64.cmake`.
- Your own copy of the game, extracted under `extracted/` (StarCraft: Ghost: `extracted/StarCraft Ghost Xbox Finn Hillbilly/`).

`scripts/18-launch-user.sh` and `recomp/game/build.sh` resolve the checkout path from `$HOME/WORKSPACE-VM/projects/xbox-on-deb` (override with `REPO_ROOT`).

### Quick start

```sh
make toolkit   # clone or fast-forward the xboxrecomp fork into refs/xboxrecomp
make build     # build ghost.exe from the recompiled sources
make           # launch it (same as make launch); stop with make stop
```

`make help` lists every target. The runtime log lands in `logs/latest-runtime.log`.

## Subsystems

### Recompilation toolkit and runtime

The toolkit lives in `refs/xboxrecomp`, a separate clone of [Modded-Software/xboxrecomp](https://github.com/Modded-Software/xboxrecomp) (a fork of `sp00nznet/xboxrecomp`). Its Python pipeline parses the XBE, finds and classifies functions, recovers calling conventions, and lifts every guest function to C. Its runtime answers the Xbox kernel, memory map, NV2A GPU (on a native D3D11 backend), APU audio, and USB input in host code, so there is no CPU emulator at run time. Runtime fixes are committed to the fork, not carried as patches here.

### Per-game layer

Each game gets a thin project that links the generated C against the runtime. For StarCraft: Ghost that is `recomp/game/` (entry point, manual overrides in `src/recomp_manual.c`). The generated tree is a build artifact:

```sh
make regen OUT=recomp/build/gen_fresh   # regenerate (reuses analysis)
make gen-diff                            # regenerate and diff against the in-tree sources
```

Corrections go in `recomp_manual.c`, `recomp/config/`, or `recomp/tools/`. Hand edits to generated code are logged locally in `recomp/game/MANUAL_PATCHES.md` (gitignored, not distributed).

### Input, recording, and video

The runtime accepts a physical Xbox pad and a keyboard-and-mouse mapping (`KBM=1`, on by default for `make launch`). Sessions record every input edge so a crash can be replayed hands-free, and the game window plus its audio can be captured to MP4 with VAAPI encoding:

```sh
make record-session SESSION=<id>   # play; input is recorded
make replay-session SESSION=<id>   # replay it without hands-on input
make record-video NAME=<id>        # then make stop-video -> logs/video-<id>.mp4
```

### Tests and performance

`recomp/tests/` launches the game, injects input off-focus, and checks input, mission reach, audio, the cloak effect, and frame rate. `make ab-perf` runs paired FPS comparisons of a runtime setting against a control.

```sh
make test                  # full suite
make test-one T=<name>     # one test by name substring
make ab-perf V=RECOMP_ASYNC_FLIP=0
```

Framework: [`recomp/tests/README.md`](recomp/tests/README.md).

### Cxbx-Reloaded path (older)

The first approach ran `Ghost.xbe` in Cxbx-Reloaded under GE-Proton, and the Win32 TGS demo (`Star*.exe`) directly under GE-Proton. Its scripts (`scripts/01` to `08`) still work, but boot takes about 5 minutes and the build is glitchy, which is why the project moved to recompilation. Notes: [`docs/00-overview.md`](docs/00-overview.md), [`docs/04-cxbx-wine-crash.md`](docs/04-cxbx-wine-crash.md).

## Games

| Game | Build | Status | Docs |
| --- | --- | --- | --- |
| StarCraft: Ghost | `Ghost.xbe`, debug-type release build, 2004-05-08, XDK 5659 | Menus and missions playable with audio; runtime defects tracked in the local, undistributed `recomp/docs/` and `recomp/diary/` notes | [`docs/02-inventory.md`](docs/02-inventory.md) |

The StarCraft: Ghost reference [wiki](wiki/README.md) covers the game, its development, and the leaked build: `cd wiki && bash tools/serve.sh` serves it on `http://127.0.0.1:18082/en/`.

## Navigation map

| Path | Contents |
| --- | --- |
| `Makefile` | Operator surface: launch, build, regen, test, record, stop |
| `recomp/game/` | StarCraft: Ghost game project and build script |
| `recomp/tools/`, `recomp/config/` | Source-map pipeline, seeds and annotations |
| `recomp/tests/` | Automated test framework |
| `recomp/docs/`, `recomp/diary/` | Recompilation design notes and per-task run diaries (local, gitignored) |
| `recomp/toolchain/` | zig MinGW toolchain file and import-lib generator |
| `refs/` | Toolkit clone and reference ports (gitignored) |
| `scripts/` | Launch, stop, regen, profiling, capture, and older Cxbx scripts |
| `docs/` | Leak inventory, research archive, Cxbx-era notes, and recomp design notes (e.g. [`docs/07-reshade-integration.md`](docs/07-reshade-integration.md)) |
| `wiki/` | Static StarCraft: Ghost reference wiki |
| `extracted/`, `emulator/`, `logs/` | Game data, Cxbx binaries, run logs (gitignored) |

## Contributing

Stop the game between runs (`make stop`). Every test or launch run gets an entry in its task diary under `recomp/diary/<task>.md` (local, gitignored), with the command, result, and error counts from the runtime log. Agent and debugging notes, runtime environment variables, and the hang-diagnosis recipe are in [`AGENTS.md`](AGENTS.md).

## Legal

Game builds supported here are copyrighted material and are not included or redistributed; supply your own. This repository contains tooling, documentation, and scripts. Cxbx-Reloaded and xboxrecomp are separate projects under their own licenses.
