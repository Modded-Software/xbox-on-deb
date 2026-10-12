# 01 — Research

## What the leak is

StarCraft: Ghost was a stealth-action spin-off of StarCraft developed by
Nihilistic Software, announced 2002, later handed to Swingin' Ape Studios and
cancelled. In February 2020 a development build leaked publicly (BetaArchive,
archive.org `starcraftghostxbox`). This repo's archive is dated 2019-12-29 and
titled "StarCraft Ghost Xbox Finn Hillbilly".

The build is from the Nihilistic era (~2003/2004, Xbox `Ghost*.xbe` headers
2004; the `Star*.exe` PE timestamps are 2002). It contains a playable Xbox
build and an older Win32 demo (the Tokyo Game Show demo).

## Key facts from prior art

Sources: BetaArchive thread `t=40850`, r/xemu threads, r/starcraft, r/TCRF,
GameRevolution coverage, consolescenenews.

- The **Xbox build runs in Cxbx-Reloaded** (HLE, no BIOS/dashboard needed).
  It is playable but glitchy and crash-prone.
- It wants **128 MB RAM** (devkit); retail Xbox has 64 MB. Emulator must be set
  to 128 MB.
- Known playable missions: Scattered Forces, Zergling Rush, Canyon Advance,
  The Fujita Pinnacle, Pinnacle Hangar, plus Borgo Refinery (commented out in
  `Misc/ghostsp.nsc`, can be re-enabled).
- Create a profile named **`Nova`** to unlock all missions.
- `Ghost.xbe` = RELEASE, `GhostR.xbe` = RETAIL-ish, `GhostU.xbe` = unknown
  variant; `_d` source-looking PDB paths inside; not a full debug build.
- Command-line switches found in the binaries: `/devmode`, `/console`, `/window`,
  `/tgs`, `/level`, `/nosound`, `/novid`.
- `/tgs` enables the Tokyo Game Show demo mode.
- The **Win32 `Star*.exe`** builds run on Windows/Wine with Direct3D 8. They
  load a menu/logo; with a **controller** (not keyboard) you can advance, but
  they crash entering the game. They load Xbox-packed sound banks and expect
  some assets from the Vampire: The Masquerade engine (`Katana`, `Foley`).
  Running creates `masquerade.ini`.
- Audio SFX in the Xbox build is partly missing under emulation.

## Emulator options considered

| Emulator | Needs BIOS? | Linux | Verdict |
|----------|-------------|-------|---------|
| Cxbx-Reloaded | No (HLE) | Windows-only app | **chosen** — known to run this title; run under GE-Proton |
| xemu | Yes (MCPX + BIOS) | Native Linux | blocked — no BIOS; also poor at raw XBE |
| dxbx | Yes | Windows-only, ancient | rejected |
| Xenia | n/a (Xbox 360) | — | irrelevant |

### Trade-off

- The **Xbox build** is the complete/full release build but requires an
  emulator. Cxbx-Reloaded is a Windows x64 D3D9 application → run under
  GE-Proton so its D3D9 output goes through DXVK → Vulkan on the Arc GPUs.
- The **Win32 demo** is native to Wine/Proton (easiest) but is the older,
  incomplete TGS demo.

Both are pursued: the Win32 demo proves the Proton+DXVK path, then the Xbox
emulator is set up for the full build.
