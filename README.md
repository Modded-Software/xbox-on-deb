# xbox-on-deb

Get the leaked **StarCraft: Ghost** development build running on Ubuntu/Debian —
both the full **Xbox** release build and the older **Win32** TGS demo — using
Steam's **GE-Proton** (Wine + DXVK + VKD3D) and **Cxbx-Reloaded** for the Xbox
executable.

> StarCraft: Ghost is a cancelled Nihilistic Software stealth-action spin-off.
> This repo does **not** contain the game. See [Legal](#legal).

---

## Features

- **Xbox release build (`Ghost.xbe`) via Cxbx-Reloaded** under GE-Proton, with
  Cxbx's D3D9 output translated to **Vulkan (DXVK)** on the GPU.
- **Win32 TGS demo (`Star*.exe`) directly under GE-Proton** (Direct3D 8).
- **Crash workaround** for Cxbx's CPU-affinity path, which uses a broken Wine
  `GetSystemCpuSetInformation` stub (see
  [`docs/04-cxbx-wine-crash.md`](docs/04-cxbx-wine-crash.md)).
- **Xbox controller support** via Wine's SDL winebus backend + a Cxbx input
  profile (full button/axis/trigger mapping).
- **Aspect-ratio fix** for Cxbx's monitor-clamp bug (square/squashed window).
- **Audio tuning** for Cxbx's emulated DirectSound streaming.
- **Retry launcher** for Cxbx's flaky XBE init (~1 in 3 launches).
- Helper scripts for screenshots, sending X11 keys/clicks, moving windows, and
  reading/writing Wine registry settings without an interactive shell.

---

## The leak: two executable families

The archive ships two very different builds. Telling them apart matters:

| Family | Files | Target | Runs how |
|--------|-------|--------|----------|
| Win32 demo | `Star.exe`, `Star_d.exe`, `Star_u.exe` | Windows, Direct3D 8 + DInput8 | GE-Proton directly |
| Xbox build | `Ghost.xbe`, `GhostR.xbe`, `GhostU.xbe` (+ `Ghost*.exe`, `.map`, `.pdb`) | Original Xbox (`xboxkrnl.exe`) | Cxbx-Reloaded |

`Ghost.exe` / `GhostR.exe` / `GhostU.exe` are **not** Windows binaries — they
are Xbox PE images with an `.exe` suffix. Only the `Star*.exe` trio is native to
Wine/Proton. Verify with:

```sh
objdump -p "extracted/StarCraft Ghost Xbox Finn Hillbilly/Ghost.exe" | grep -i subsystem
# Subsystem 0000000e (Windows CUI?) -> actually the Xbox kernel subsystem
```

(`Ghost*.exe` import only `xboxkrnl.exe`.)

---

## Requirements

| Component | Notes |
|-----------|-------|
| Ubuntu/Debian, X11 or XWayland | scripts assume an X display (`DISPLAY=:0`) |
| Steam + **GE-Proton** | tested with `GE-Proton11-1`; install under `~/.steam/root/compatibilitytools.d/` |
| **Cxbx-Reloaded** | Windows build, extracted to `emulator/` (excluded from git) |
| Mesa Vulkan driver | DXVK → Vulkan (tested: Intel ANV; works on any Vulkan GPU) |
| `7z` | extract the leak |
| Python 3 | helpers use only stdlib + `ctypes` (X11), `xwd2png.py` needs Pillow |

Get Cxbx-Reloaded from <https://github.com/Cxbx-Reloaded/Cxbx-Reloaded/releases>
and extract it so `emulator/cxbx.exe` exists.

---

## Quick start

```sh
# 1. Extract the leak into extracted/
7z x "res/StarCraft Ghost Xbox Finn Hillbilly.7z" -oextracted/

# 2. Create the GE-Proton prefix
bash scripts/01-setup-prefix.sh

# 3. (One-time) put the prefix on Windows 7 so Cxbx avoids Wine's broken
#    CPU-set API. Without this, Ghost.xbe crashes on init.
source scripts/config.env
WINEPREFIX="$SCGHOST_PREFIX/pfx" \
  "$GE_PROTON_DIR/files/bin/wine" reg add "HKCU\\Software\\Wine" \
  /v Version /d win7 /f

# 4. Play the Xbox release build (retries the flaky init until it renders)
bash scripts/06-retry-launch.sh \
  "extracted/StarCraft Ghost Xbox Finn Hillbilly/Ghost.xbe"

# ...or the native Win32 demo
RENDERER=dxvk bash scripts/02-launch-win32-demo.sh
```

---

## Scripts

| Script | Purpose |
|--------|---------|
| `01-setup-prefix.sh` | Create the `~/Games/scghost-prefix` GE-Proton prefix |
| `02-launch-win32-demo.sh` | Run the Win32 `Star*.exe` demo (`RENDERER=dxvk\|wine`) |
| `03-launch-xbox-build.sh` | Run Cxbx under GE-Proton with an XBE |
| `04-setup-wine7.sh` | (Optional) Wine 7 prefix via `GE-Proton7-55` |
| `05-launch-xbox-wine7.sh` | Launch Cxbx under the Wine 7 prefix |
| `06-retry-launch.sh` | Retry Cxbx's flaky XBE init; reports success rate |
| `07-set-audio-buffer.sh` | Patch Cxbx's `streamAhead` default (ms) in `cxbxr-emu.dll` |
| `08-set-virtual-desktop.sh` | Toggle Wine's virtual desktop (`on\|off [WxH]`) |
| `screenshot.sh` / `xwd2png.py` | Capture an X window to PNG |
| `sendkey.py` | Send a key or `click:X:Y` via XTest (no `xdotool`) |
| `movewin.py` | Move an X11 window by title (no `wmctrl`) |
| `gamepad.py` | Inspect/verify the controller through SDL |
| `portal_screenshot.py` | Full-screen capture via the XDG portal (GPU windows) |
| `config.env` | Shared paths; auto-detects the installed GE-Proton |

---

## Known issues & tuning

### The render window is square / the image is squashed

Cxbx sizes its window to `GetWindowRect(GetDesktopWindow())`
(`WndMain.cpp`), i.e. the **primary monitor**. If the primary display is a
portrait/rotated panel narrower than the requested resolution, Cxbx clamps the
window (e.g. `1920x1080` → `1080x1080`) and the image distorts. `Maintain
Aspect Ratio` cannot fix a square window.

Fix: pick a 16:9 resolution that fits the primary monitor (e.g. **1024x576** on
a 1080-wide portrait primary), or run with a wide monitor as primary. DXVK
reports the real swapchain in its log:

```
D3D9DeviceEx::ResetSwapChain: Width 1920 Height 1080
Presenter: Buffer size: 1080x1080     # square → clamped
```

### Cxbx crashes with `0xC0000005` at init

Wine's `GetSystemCpuSetInformation` stub is broken. Fixes: set the prefix to
Windows 7 (above) and/or `[hack] UseAllCores = true` in `emulator/settings.ini`
(bypasses the affinity policy entirely). Full write-up:
[`docs/04-cxbx-wine-crash.md`](docs/04-cxbx-wine-crash.md).

### Cxbx rewrites `settings.ini` on exit

Any manual setting is lost when the GUI closes normally. Set values while Cxbx
is **not** running, and either force-kill the session or make the file
read-only (`chmod 444 emulator/settings.ini`).

### Choppy audio

The host audio stack may be perfectly clean (`pw-top` shows `ERR=0`) while
Cxbx's emulated DirectSound still crackles. Tune at runtime with **F1 →
DSBuffer Visualization → Buffering Controls** ("Stream ahead (ms)"), or patch
the compiled default with `scripts/07-set-audio-buffer.sh <ms>`.

### Flaky launch

The XBE init only succeeds some of the time. `scripts/06-retry-launch.sh`
detects success by looking for `ResetSwapChain` in the run log and retries.

---

## Layout

```
res/                     original .7z (not committed)
extracted/               game data (not committed)
emulator/                Cxbx-Reloaded binaries + settings.ini (not committed)
docs/                    research, inventory, plan, crash write-up
scripts/                 setup, launcher and helper scripts
wiki/                    static reference wiki (see wiki/README.md)
```

## Docs

Start at [`docs/00-overview.md`](docs/00-overview.md).

| Doc | Contents |
|-----|----------|
| [00-overview](docs/00-overview.md) | Goal, machine, status |
| [01-research](docs/01-research.md) | Background and prior art |
| [02-inventory](docs/02-inventory.md) | What is in the leak (with MD5s) |
| [03-plan](docs/03-plan.md) | Approach and decision log |
| [04-cxbx-wine-crash](docs/04-cxbx-wine-crash.md) | The `0xC0000005` init crash and fix |
| [05-research-archive](docs/05-research-archive.md) | Archive of official/leaked/community sources (links + gitignored artifacts) |
| [06-vision-vs-build-gap-analysis](docs/06-vision-vs-build-gap-analysis.md) | Stated vision vs. what the May 2004 build contains |

## Wiki

[`wiki/`](wiki/README.md) is a static, documents-first reference wiki about the
game, its development, and the leaked build. Every route is a plain HTML
document; there is no build step. The design is a Retro StarCraft HUD, and the
pages carry real archived imagery (screenshots, key art, concept art) pulled
from the preserved official site. Images are local and gitignored; the pipeline
is in [`scripts/ghost-research/images.py`](scripts/ghost-research/images.py) and
the art direction is in [`wiki/docs/DESIGN-DIRECTION.md`](wiki/docs/DESIGN-DIRECTION.md).
Serve it with the bundled static server:

```sh
cd wiki && bash tools/serve.sh   # http://127.0.0.1:18082/en/
```

Check the document contract, image integrity, anti-slop lint, and page-weight
budgets with `bash wiki/tools/run-tests.sh`.

## Legal

The StarCraft: Ghost development build is unreleased, copyrighted material that
leaked publicly; it is **not** included here and must not be redistributed.
This repository contains only tooling, documentation and scripts. Cxbx-Reloaded
is a separate GPL project and is not redistributed here.
