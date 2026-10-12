# 00 — Overview

## Goal

Get the executables from the leaked StarCraft: Ghost development build running
on this machine, with working rendering (Vulkan or OpenGL). Keep notes under
`docs/` as work proceeds. Stop only on blockers or genuine ambiguity.

## Machine

| Item | Value |
|------|-------|
| OS | Ubuntu 24.04.4 LTS (noble) |
| CPU | 32 threads |
| RAM | 94 GiB |
| GPU | 2× Intel Arc A770 (DG2), `renderD128` + `renderD129` |
| Vulkan | 1.4.318, Mesa ANV (Intel open-source) + llvmpipe |
| Windows stack | Steam installed, **GE-Proton11-1** (Wine + DXVK 2.7.1 + VKD3D-Proton) |
| Wine | system wine 9.0 (fallback) |

DXVK 2.7.1 ships `d3d8.dll`, so the Win32 Direct3D 8 demo can render through
Vulkan on the Arc GPUs.

## Status

| Target | Status |
|--------|--------|
| Extract leak | done |
| Inventory | done |
| Win32 `Star*.exe` under GE-Proton | runs (menu/logo; crashes entering gameplay) |
| Xbox `Ghost.xbe` under Cxbx-Reloaded | runs (boots, renders; playable but glitchy) |
| Xbox controller input | working (XInput via winebus + Cxbx profile) |
| Aspect-ratio / render-window fix | working (see README "Known issues") |
| Audio | reproduces, but choppy inside Cxbx (host stack is clean) |

See [`03-plan.md`](03-plan.md) for the decision log and
[`04-cxbx-wine-crash.md`](04-cxbx-wine-crash.md) for the init-crash fix.

## Research

| Doc | Contents |
|-----|----------|
| [05-research-archive](05-research-archive.md) | Archive of official, leaked and community sources (links + gitignored artifacts) |
| [06-vision-vs-build-gap-analysis](06-vision-vs-build-gap-analysis.md) | Stated vision vs. what the May 2004 build actually contains |
