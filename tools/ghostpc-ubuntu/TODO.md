# GhostPC Ubuntu TODO

Status: builds, boots, loads a level, and reaches gameplay under GE-Proton and
system Wine. Remaining issues are tracked here.

## Player-visible

- [x] Flat gray/blue patches and the white projected-shadow silhouette are
      present in the official MSVC v2026-10-29 build under the same Wine, so
      they are Wine/prototype-level, not a cross-build regression. Force
      re-upload (patch 0005) also changes nothing.
- [x] The blue floor area near the crates is water/fog, not a missing texture
      (confirmed by moving the camera).
- [ ] Compare the same scene on Windows D3D9 to see whether wined3d is the
      cause of the white shadows/untextured NPC silhouettes.
- [ ] Verify movement, aim, and all mkb bindings hands-on (user-verified only).
- [ ] Check audio levels and looping in the first mission.

## Crashes / hangs

- [x] Proton stall: GE-Proton11-1's DXVK 2.7 dev build logs
      `VK_ERROR_DEVICE_LOST` on Intel DG2 (Mesa 25.2.8, i915) after a level
      load. GE-Proton7-55 (DXVK 2.1) and wined3d both run at 30 fps.
- [x] Bisect: release DXVK 2.2, 2.3.1, 2.4.1, 2.5.3, 2.6.2, and 2.7.1 all
      run with no `DEVICE_LOST`. The failure is GE-Proton11-1's bundled
      master snapshot (`v2.7.1-822`), not release 2.7.1.
- [ ] Report the Arc device loss to DXVK (master after 2.7.1) / Mesa.
- [ ] Confirm the `gameWorld_LoadWorld` detour and `cSaveData::Restore` detour
      on restarts (`levelscript.cpp`).

## Loader / base address

- [ ] Wine keeps `0x00400000` by the time `MapImage` runs, so the image still
      relocates to `~0x022C0000`. `baseHold` in patch 0002 is a no-op because
      the region is already taken. Find a way to reserve the base before the
      CRT heap grows, or confirm relocation is fully safe now.
- [ ] Decide whether to keep `patch-pe.py` (DllCharacteristics ASLR/NX off).

## Build / tooling

- [ ] Keep the 281 `xb_`/`kx_` hooks checked by `check-hooks.sh` when the
      upstream map changes.
- [ ] Add a basic check: build, launch with `-level 1_2_1_Miners_Bunker`, assert
      `level load` and a frame counter above N, then stop.
- [ ] Remove or gate the temporary diagnostics (`GHOSTPC_UBUNTU_EXIT_TRACE`,
      baseHold logging) once the texture/hang issues are understood.
- [ ] Document the `push [mem]; ret` rule for clang `-fasm-blocks`
      (patch 0003): `jmp dword ptr [mem]` is miscompiled.
