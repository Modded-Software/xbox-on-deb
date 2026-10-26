#!/bin/bash
# Build dist/StarCraft-Ghost-Setup.exe (Win32 installer + appended payload).
set -euo pipefail
ROOT="${REPO_ROOT:-$HOME/WORKSPACE-VM/projects/xbox-on-deb}"
cd "$ROOT"
RES="$ROOT/res/starcraft-ghost-archive/images"
WIKI="$ROOT/wiki/site/assets/media"
ASSETS="${INSTALLER_ASSETS:-$ROOT/res/installer-assets}"
BUILD="$ROOT/recomp/installer/build"
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
for required in logo.png eurostile.otf; do
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

chmod +x "$ROOT/recomp/toolchain/bin/x86_64-w64-mingw32-rc"

cmake -S "$ROOT/recomp/installer" -B "$BUILD" -G "Unix Makefiles" \
    -DCMAKE_TOOLCHAIN_FILE="$ROOT/recomp/toolchain/zig-windows-x64.cmake" \
    -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD" --target StarCraftGhostSetup GhostRecompUninstall -j "$(nproc)"

mkdir -p "$DIST"
uv run python "$ROOT/recomp/installer/tools/pack.py" \
    --setup "$BUILD/StarCraftGhostSetup.exe" \
    --out "$DIST/StarCraft-Ghost-Setup.exe" \
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
    --entry "2|assets/logo.png|$ASSETS/logo.png" \
    --entry "2|assets/eurostile.otf|$ASSETS/eurostile.otf"

uv run python "$ROOT/recomp/installer/tools/pack.py" --verify "$DIST/StarCraft-Ghost-Setup.exe"
sha256sum "$DIST/StarCraft-Ghost-Setup.exe" > "$DIST/StarCraft-Ghost-Setup.exe.sha256"
echo "built $DIST/StarCraft-Ghost-Setup.exe"
