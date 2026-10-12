# 02 — Inventory

Source: `res/StarCraft Ghost Xbox Finn Hillbilly.7z`
(486,276,583 bytes, LZMA2, solid). Extracted to
`extracted/StarCraft Ghost Xbox Finn Hillbilly/` — 7560 files, 1,110,156,657 bytes.

## Executables

### Xbox PE images (`Subsystem = XBOX`, import `xboxkrnl.exe`)

| File | Size | Notes |
|------|------|-------|
| `Ghost.xbe` | 4,280,320 | release build |
| `GhostR.xbe` | 3,997,696 | "retail" variant |
| `GhostU.xbe` | 3,751,936 | variant |
| `update.xbe` | 2,387,968 | updater |
| `Ghost.exe` | 5,382,784 | Xbox PE with `.exe` name (+ `Ghost.map`, `Ghost.pdb`) |
| `GhostR.exe` | 5,087,904 | Xbox PE with `.exe` name |
| `GhostU.exe` | 4,834,208 | Xbox PE with `.exe` name (+ `GhostU.map`) |

> The `Ghost*.exe` files are Xbox binaries, **not** Win32. Confirmed with
> `file` and `objdump -p` (subsystem 0xe, single import `xboxkrnl.exe`).

### Win32 PE images (Direct3D 8 + DirectInput 8)

| File | Size | Imports |
|------|------|---------|
| `Star.exe` | 2,957,363 | KERNEL32, USER32, GDI32, WINMM, ADVAPI32, **d3d8**, **DINPUT8** |
| `Star_d.exe` | 6,869,043 | same (+ `Star_d.pdb`) |
| `Star_u.exe` | 2,506,752 | same |

## Data tree

```
3D/            Anims, Materials, Models, Motions, Terrains
Cutscenes/     .bik / .vid cinematics
Levels/        7 .nil/.nsd/.npd level sets + menu
Materials/     Colors, Common, Effects, Glass, Lights, Metal, Organic,
               Shaders, Stone, Terrain, Wood
Misc/          UI templates (.nlt), sequences (.nco), game.nls/.nlu/.nlx,
               ghostsp.nsc (mission list), sound-related bins
Sounds/        Xbox sound banks
UI/            FONTS, Icons, Materials
VertexShaders/ XBox/ (precompiled vertex shader binaries)
Video/         Bink video, attract mode
media/         ArialUni.Ttf, dlcustom.xpr, Sound.xsb, Wave.xwb
```

## Command-line switches (strings)

From `Star*.exe` and known from the Xbox binaries:
`/devmode`, `/console`, `/window`, `/tgs`, `/level`, `/nosound`.

## MD5

```
Ghost.exe      d3732e4fb6d8579f82e289abd9689ac3
GhostR.exe     87f263aaad97090423726c080aa8229b
GhostU.exe     496df0e3079393ec12df3296cc3f8299
Star.exe       50d214eae8b70f4e61e58df4391dc660
Star_d.exe     d8283025dce251c9e9ec0db58cf96a43
Star_u.exe     9965dc86f8cfe5647bf450a87cd6e04c
Ghost.xbe      dbf5b24ba8d39a62155d695986b35b00
GhostR.xbe     2f931e4a9d61dbf37c0368dd173a12c5
GhostU.xbe     3d76e7f307cd1e2cc7f2ab85922b355d
update.xbe     82b2ea8b1d7bac349634556e1b4f9817
```
