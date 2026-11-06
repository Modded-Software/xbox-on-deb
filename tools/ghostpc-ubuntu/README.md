# GhostPC on Ubuntu (cross-build)

Builds `refs/GhostPC` (Tamamo-no-Bae/GhostPC, a native Win32 host for the
StarCraft: Ghost Xbox prototype) on Ubuntu with the repo's zig/mingw-w64
toolchain, so the port can be tested under Wine.

The upstream project targets Visual Studio 2019 Build Tools (MSVC x86) and
Direct3D 9. `build.sh` uses the same i686 mingw sysroot the repo already ships
for the XP installer, and adds the Ubuntu layer this needs:

| Problem | Fix |
|---|---|
| MSVC SEH (`__try`/`__except`) is not available under mingw | `compat/ghostpc_ubuntu_compat.h` maps it to a VEH + `setjmp` frame stack (`compat/ghostpc_ubuntu_seh.cpp`) |
| MSVC inline asm (`__asm { ... }`) | clang's `-fms-extensions -fasm-blocks` |
| Implicit function-pointer → `void *` (MSVC extension) | three overloads added by `patches/0001-mingw-compat.patch` |
| `select()` const mismatch in mingw winsock | cast in the same patch |
| `#pragma comment(lib, "xinput9_1_0")` | import libraries generated from zig's `.def` files |
| zig's default `kernel32` is XP-baseline | a complete `libkernel32.a` is generated from zig's Windows 7+ `.def` |

## Build

```bash
bash tools/ghostpc-ubuntu/build.sh
```

Output: `tools/ghostpc-ubuntu/build/GhostPC.exe` (PE32 GUI, i386).
Set `JOBS=N` to change parallelism.

`refs/GhostPC` must exist (clone it; it is not vendored):

```bash
git clone https://github.com/Tamamo-no-Bae/GhostPC refs/GhostPC
```

The build copies the sources to `build/src/`, so the clone stays pristine; the
only source changes are the tracked patch files under `patches/`.

## Run under Wine

```bash
bash tools/ghostpc-ubuntu/run-wine.sh
```

This builds a scratch game directory (`run/`), links the game data from
`recomp/game/game/`, writes `ghostpc.ini` with the keyboard/mouse profile and
no settings dialog, then starts `GhostPC.exe` under GE-Proton (see
`scripts/config.sh`). Use `RENDERER=wine` to force wined3d. Pass game arguments
through `GhostPC.exe`, for example `-level 1_2_1_Miners_Bunker` for a direct
level load.

**Proton/DXVK note (Intel Arc A770, Mesa 25.2.8, i915):** GE-Proton11-1
ships a DXVK master snapshot (`v2.7.1-822`). After a level load it logs
`vkWaitForPresentKHR failed: VK_ERROR_DEVICE_LOST` and the game stops at
frame 6. The official MSVC exe does the same, so this is not the cross-build.

Release DXVK 2.2, 2.3.1, 2.4.1, 2.5.3, 2.6.2, and 2.7.1 do not lose the
device. The bad build is the master snapshot Proton 11 bundles, not release
2.7.1. Working options:

```bash
GHOSTPC_GE_PROTON=GE-Proton7-55 bash tools/ghostpc-ubuntu/run-wine.sh
RENDERER=wine bash tools/ghostpc-ubuntu/run-wine.sh
```

`GHOSTPC_GE_PROTON` is a directory name under Steam's `compatibilitytools.d`.
If `run/d3d9.dll` exists (the x32 DLL from a release `dxvk-<ver>.tar.gz`),
`run-wine.sh` sets `WINEDLLOVERRIDES=d3d9=n,b` and uses that DLL instead of
Proton's bundled DXVK.

Logs:

- `run/ghostpc.log` (GhostPC's own log)
- `run/ghostpc.prev.log`
- `logs/ghostpc-ubuntu-<timestamp>.log` (Wine stdout/stderr)
- `run/ghostpc-ubuntu-build.log` (build stamp + library versions, written by the
  instrumentation probe)

The launch uses `GHOSTPC_UBUNTU_TRACE=1`, which logs every `__try` exception the
SEH layer catches and every VEH pass-through to the build log.

## Instrumentation

`compat/ghostpc_ubuntu_probe.cpp` is compiled into the exe. It writes a build
stamp (compiler, date, `wine --version`, DLLs present) and exposes:

| Env var | Effect |
|---|---|
| `GHOSTPC_UBUNTU_TRACE=1` | log caught SEH exceptions (code + address) |
| `GHOSTPC_UBUNTU_EXIT_TRACE=1` | log callers of `ExitProcess`/`ExitThread`/`RtlExitUser*` (patch 0004) |
| `GHOSTPC_UBUNTU_LOG=<path>` | build-stamp / trace log path (default: exe dir) |

Patches applied on top of the upstream sources:

| Patch | Purpose |
|---|---|
| `0001-mingw-compat.patch` | function-pointer overloads, `select()` cast |
| `0002-loader-map-at-preferred-base.patch` | keep `0x00400000` free while reading the image (diagnostic; currently a no-op under Wine) |
| `0003-indirect-jmp.patch` | clang `-fasm-blocks`: `jmp dword ptr [mem]` becomes `push [mem]; ret` |
| `0004-exit-trace.patch` | optional `ExitProcess`/`ExitThread` logging |
| `0005-force-texture-upload.patch` | `GHOSTPC_UBUNTU_FORCE_UPLOAD=1` re-uploads every texture (diagnostic for stale/black textures) |

`patch-pe.py` clears `DYNAMIC_BASE`/`NX_COMPAT` so the host exe loads at its
preferred `0x10000000`.

## Reference build

To tell a cross-build regression from a Wine/prototype issue, run the official
MSVC build from the upstream release under the same Wine:

```bash
curl -L -o /tmp/GhostPC_Patch.zip \
  https://github.com/Tamamo-no-Bae/GhostPC/releases/download/v2026-10-29/GhostPC_Patch.zip
unzip -o /tmp/GhostPC_Patch.zip GhostPC.exe -d /tmp/ref
cp /tmp/ref/GhostPC.exe tools/ghostpc-ubuntu/run/GhostPC_ref.exe
```

`run/GhostPC_ref.exe` then behaves like the normal build (same game directory).
This was used to confirm that the white projected shadows and the GE-Proton
frame-6 stall are not caused by the Ubuntu cross-build.

## Status

The build boots, loads a level, and reaches gameplay under system Wine. Some
textures/effects are missing. Under GE-Proton the same build can stop
presenting after a level load. See `TODO.md`.

`check-hooks.sh` runs the upstream `checkhooks.py` against the game's
`Ghost.map` and the linked exe's map, when both are available.
