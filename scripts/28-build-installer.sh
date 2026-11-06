#!/bin/bash
# Build dist/StarCraft-Ghost-Setup.exe (Win32 installer + appended payload).
#
#   bash scripts/28-build-installer.sh          # installer for 64-bit Windows
#   ARCH=x86 bash scripts/28-build-installer.sh # 32-bit setup, runs on XP
#
# ARCH=x86 builds only the setup/uninstaller as i686 PE32 (dist
# StarCraft-Ghost-Setup-x86.exe). The payload GhostRecomp.exe stays x86_64:
# 32-bit XP can run the installer, not the game.
set -euo pipefail
ROOT="${REPO_ROOT:-$HOME/WORKSPACE-VM/projects/xbox-on-deb}"
cd "$ROOT"
RES="$ROOT/res/starcraft-ghost-archive/images"
WIKI="$ROOT/wiki/site/assets/media"
ASSETS="${INSTALLER_ASSETS:-$ROOT/res/installer-assets}"
ARCH="${ARCH:-x64}"
case "$ARCH" in
    x64)
        TOOLCHAIN="$ROOT/recomp/toolchain/zig-windows-x64.cmake"
        BUILD="$ROOT/recomp/installer/build"
        DIST_NAME="StarCraft-Ghost-Setup.exe"
        ;;
    x86)
        TOOLCHAIN="$ROOT/recomp/toolchain/zig-windows-x86.cmake"
        BUILD="$ROOT/recomp/installer/build-x86"
        DIST_NAME="StarCraft-Ghost-Setup-x86.exe"
        ;;
    *)
        echo "ARCH must be x64 or x86 (got '$ARCH')" >&2
        exit 2
        ;;
esac
DIST="$ROOT/dist"
EXE="$ROOT/recomp/game/build/ghost.exe"

if [ ! -f "$EXE" ] || [ "$ROOT/recomp/game/src/main.c" -nt "$EXE" ]; then
    bash "$ROOT/recomp/game/build.sh"
fi

resolve() {
    id="$1"
    if [ -f "$RES/${id}.jpg" ]; then
        echo "$RES/${id}.jpg"
        return
    fi
    if [ -f "$WIKI/${id}.jpg" ]; then
        echo "$WIKI/${id}.jpg"
        return
    fi
    echo "missing splash image: $id" >&2
    echo "run: .venv-wiki/bin/python scripts/ghost-research/images.py" >&2
    exit 1
}

TITLE_SRC="${SCGHOST_TITLE_WAV:-$ASSETS/title.wav}"
TITLE_WAV="$BUILD/title.wav"
if [ ! -f "$TITLE_SRC" ]; then
    echo "missing title music: $TITLE_SRC" >&2
    echo "installer media is not distributed with this repository." >&2
    echo "see recomp/installer/README.md for the required files." >&2
    exit 1
fi
if [ ! -f "$ASSETS/ghost.ico" ]; then
    uv run python "$ROOT/recomp/installer/tools/make_icon.py" "$ASSETS/ghost.ico"
fi
for required in logo.png eurostile.otf MENU_ITEM_HOVER.wav MENU_ITEM_SELECT.wav ghost.ico; do
    if [ ! -f "$ASSETS/$required" ]; then
        echo "missing installer asset: $ASSETS/$required" >&2
        echo "installer artwork and fonts are not distributed with this repository." >&2
        echo "see recomp/installer/README.md for the required files." >&2
        exit 1
    fi
done
mkdir -p "$BUILD"
ffmpeg -y -i "$TITLE_SRC" -ac 1 -ar 22050 -sample_fmt s16 "$TITLE_WAV"

MENU=$(resolve keyart-terranbase)
LOCATE=$(resolve keyart-nova-sideview)
OPTIONS=$(resolve keyart-comic)
PROGRESS=$(resolve keyart-battlecruisers)
FINISH=$(resolve keyart-nova2)
ABOUT=$(resolve art-040)
REPAIR=$(resolve keyart-nova-face)
LAUNCH=$(resolve art-012)

chmod +x "$ROOT/recomp/toolchain/bin/x86_64-w64-mingw32-rc" "$ROOT/recomp/toolchain/bin/i686-w64-mingw32-rc"

cmake -S "$ROOT/recomp/installer" -B "$BUILD" -G "Unix Makefiles" \
    -DCMAKE_TOOLCHAIN_FILE="$TOOLCHAIN" \
    -DCMAKE_BUILD_TYPE=Release \
    -DGHOST_ASSET_DIR="$ASSETS"
cmake --build "$BUILD" --target StarCraftGhostSetup GhostRecompUninstall -j "$(nproc)"

# XP refuses images with subsystem version > 5.x; zig writes 6.0.
if [ "$ARCH" = "x86" ]; then
    uv run python "$ROOT/recomp/installer/tools/pe_xp.py" \
        "$BUILD/StarCraftGhostSetup.exe" "$BUILD/GhostRecompUninstall.exe"
fi

mkdir -p "$DIST"
uv run python "$ROOT/recomp/installer/tools/pack.py" \
    --setup "$BUILD/StarCraftGhostSetup.exe" \
    --out "$DIST/$DIST_NAME" \
    --entry "1|GhostRecomp.exe|$EXE" \
    --entry "1|GhostRecomp-Uninstall.exe|$BUILD/GhostRecompUninstall.exe" \
    --entry "2|assets/menu.jpg|$MENU" \
    --entry "2|assets/locate.jpg|$LOCATE" \
    --entry "2|assets/options.jpg|$OPTIONS" \
    --entry "2|assets/progress.jpg|$PROGRESS" \
    --entry "2|assets/finish.jpg|$FINISH" \
    --entry "2|assets/about.jpg|$ABOUT" \
    --entry "2|assets/repair.jpg|$REPAIR" \
    --entry "2|assets/launch.jpg|$LAUNCH" \
    --entry "2|assets/title.wav|$TITLE_WAV" \
    --entry "2|assets/MENU_ITEM_HOVER.wav|$ASSETS/MENU_ITEM_HOVER.wav" \
    --entry "2|assets/MENU_ITEM_SELECT.wav|$ASSETS/MENU_ITEM_SELECT.wav" \
    --entry "2|assets/logo.png|$ASSETS/logo.png" \
    --entry "2|assets/eurostile.otf|$ASSETS/eurostile.otf" \
    --entry "2|ghost.ico|$ASSETS/ghost.ico"

uv run python "$ROOT/recomp/installer/tools/pack.py" --verify "$DIST/$DIST_NAME"
sha256sum "$DIST/$DIST_NAME" > "$DIST/$DIST_NAME.sha256"
echo "built $DIST/$DIST_NAME"
