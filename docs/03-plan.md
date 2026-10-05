# 03 — Plan

## Approach

Follow the `windows-on-deb` conventions: `scripts/config.env`, GE-Proton for
Windows binaries, `~/Games/` for prefixes, launcher scripts, desktop entries.

### Track A — Win32 demo under GE-Proton (Direct3D 8)

1. Create a dedicated GE-Proton prefix, e.g. `~/Games/scghost-prefix`.
2. Launch `Star_u.exe` (and `Star_d.exe`) from the extracted data directory so
   relative asset paths resolve.
3. Force DXVK (Vulkan) for d3d8, confirm it lands on an Arc A770.
4. Fall back to wined3d (OpenGL) if DXVK d3d8 misbehaves — this also exercises
   the OpenGL-vs-Vulkan comparison the task asks for.
5. Provide a controller mapping if the menu requires a gamepad (DInput8).

### Track B — Xbox release build via Cxbx-Reloaded (Direct3D 9)

1. Obtain a Cxbx-Reloaded Windows release.
2. Run it under GE-Proton; DXVK translates its D3D9 output to Vulkan.
3. Configure: 128 MB RAM, point at `extracted/.../Ghost.xbe`, controller map.
4. Capture logs and screenshots.

### Rendering experiments

Both Arc A770s are exposed. Use `DRI_PRIME` / `VK_ICD_FILENAMES` and the
Mesa `ANV` driver to pin a run to one card or the other, and compare
DXVK (Vulkan) vs wined3d (OpenGL).

## Decision log

| Date | Decision | Why |
|------|----------|-----|
| 2026-10-05 | Use GE-Proton, not system wine | Matches sibling repo; DXVK 2.7.1 has d3d8 |
| 2026-10-05 | Cxbx-Reloaded for Xbox build | Only sane emulator without a BIOS dump |
| 2026-10-05 | Do Win32 demo first | Fastest proof that rendering works end to end |
| 2026-10-05 | Set Cxbx prefix to Windows 7 + retry loop | Avoids Wine's broken `GetSystemCpuSetInformation`; see docs/04-cxbx-wine-crash.md |

## Open questions / blockers

- No Xbox BIOS dump available for xemu (not needed for Cxbx).
- ~~Cxbx init crash under Wine~~ — worked around (Win7 prefix + retry); see
  `docs/04-cxbx-wine-crash.md`. Launch is still flaky (~1 in 3).
- After booting, the Xbox build reaches the intro/splash then a black frame.
- Controller required for the Win32 demo menu (keyboard reportedly ignored).
