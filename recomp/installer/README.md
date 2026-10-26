# StarCraft: Ghost recompiled installer

Win32 setup program that installs `GhostRecomp.exe` beside the game data and
provisions the GNOME/Proton launch path. Built by
`bash scripts/28-build-installer.sh` into `dist/`.

Only source is checked in. Artwork, fonts and media are **not** distributed
with this repository; each user must supply their own copies with the file
names below. `scripts/28-build-installer.sh` fails with instructions when a
file is missing.

## Required media (`res/installer-assets/`, gitignored)

| File | Purpose |
|---|---|
| `logo.png` | title logo, transparent PNG (1899x560 works well) |
| `eurostile.otf` | UI font (Eurostile); a licensed commercial face is required |
| `title.wav` | installer background music (converted to mono 22.05 kHz at build) |

Override the directory with `INSTALLER_ASSETS=<dir>` and the music file with
`SCGHOST_TITLE_WAV=<file>`.

Do not commit these files. `logo.png` and the splash images are derivative of
Blizzard Entertainment artwork, and `eurostile.otf` is licensed to the user.
`res/` is ignored for exactly this reason.

## Required splash images

Resolved at build time from `res/starcraft-ghost-archive/images/` (or
`wiki/site/assets/media/`), also gitignored:

`keyart-terranbase`, `keyart-nova-sideview`, `keyart-comic`,
`keyart-battlecruisers`, `keyart-nova2`, `art-040` (About), `keyart-nova-face`,
`art-012` (Launch), each as `<id>.jpg`.

## Output

- `dist/StarCraft-Ghost-Setup.exe` (+ `.sha256`), gitignored.
- The payload contains the game executable, the uninstaller, the splash/logo
  art and the title music. Ship it only where you are allowed to redistribute
  those assets.
