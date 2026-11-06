# GhostPC vs the static-recomp DX11 path

Two independent ways to run the leaked StarCraft: Ghost Xbox build in this
repo. GhostPC is a drop-in Win32 host that runs the original x86 `Ghost.exe`
and replaces the Xbox libraries. The active path in this repo is static
recompilation of the same x86 to C with a native D3D11 backend.

## At a glance

| | GhostPC (`tools/ghostpc-ubuntu`) | Recomp path (`recomp/game`, `refs/xboxrecomp`) |
|---|---|---|
| Executable | Original Xbox `Ghost.exe` + `Ghost.map`, loaded as a PE image | `ghost.exe` rebuilt from lifted C (`recomp/game/src/recomp/gen/`) |
| CPU model | Native x86, runs on the host CPU | Lifted C, compiled by the host C compiler |
| CPU fixes | In-place byte patches and detours at runtime | Applied to lifted code at generation or hand-edited in `gen/` |
| Memory model | Loads `Ghost.exe` at its preferred `0x00400000`; Xbox addresses used as-is | Xbox memory layout emulated (`xbox_memory_layout.c`) |
| Graphics API | D3D8/NV2A calls translated to D3D9, shaders to HLSL (`src/d3d_*`, `src/shader*`) | NV2A pushbuffer executed by a native D3D11 backend (`nv2a_pb_exec.c`, `nv2a_gpu_d3d11.cpp`) |
| Presentation | D3D9 swap chain (DXVK under Proton) | GDI blit by default, optional D3D11/DXGI swap chain (`present_d3d11.cpp`) for ReShade |
| Audio | DirectSound/XACT on XAudio2 | APU emulation / XAudio2 bridge |
| Input | Keyboard+mouse or XInput, Xbox controller protocol emulated | USB/OHCI + XInput, KBM mapping (`KBM=1`) |
| Kernel/XAPI | Win32 wrappers and traps (`loader.cpp`, `kernel.cpp`, `xapi.cpp`) | `kernel_bridge.c` and toolkit kernel services |
| Threading | Game threads run natively | Guest threads scheduled by the runtime |
| Debugging | `ghostpc.log`, symbol map, detours, minidump | `RECOMP_*` env vars, watchdog, symbol map, crash dumps |
| Build | MSVC upstream; Ubuntu cross-build via `tools/ghostpc-ubuntu` | CMake/ninja via `recomp/game/build.sh` |
| Portability | Windows-first; Ubuntu via Wine/Proton | Linux-first |
| Current state | Boots to gameplay on Ubuntu, some textures missing | Reference path, ReShade/DX11 work continues |

## Consequences

- **GhostPC** reaches gameplay quickly because the original code and its
  absolute addresses run unchanged. The cost is a Wine/Proton dependency and
  in-place runtime patching that must track the exact prototype build.
- **Static recompilation** has no Wine dependency and gives clean C debugging,
  but every Xbox function and GPU method must be lifted and implemented.
- GhostPC's D3D9+HLSL translation is a separate renderer from the recomp
  D3D11 backend; shader or texture bugs in one do not imply the other.
- GhostPC's loader fixes are useful reference material for recomp: the
  `gameWorld_LoadWorld` detour behavior matches `levelscript.cpp` in the
  recomp path.

## Ubuntu tooling

`tools/ghostpc-ubuntu/` cross-builds GhostPC with the repo's zig MinGW
toolchain, applies the Ubuntu patches, and launches it under GE-Proton
or system Wine. See its `README.md` for the build/run/check commands.

GE-Proton11-1 ships a DXVK master snapshot that loses the Intel Arc device (`VK_ERROR_DEVICE_LOST`) after a level load. GE-Proton7-55, wined3d, and release DXVK 2.2 through 2.7.1 do not. See `tools/ghostpc-ubuntu/README.md`.
