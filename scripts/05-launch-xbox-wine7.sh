#!/bin/bash
set -euo pipefail

# Launch Cxbx-Reloaded under GE-Proton7 (Wine 7.0), the last Wine version
# Cxbx-R documents as working.
#
# Usage: 05-launch-xbox-wine7.sh /path/to/Game.xbe
#   RENDERER=dxvk (default) | RENDERER=wine

source "$PWD/scripts/config.env"

WT_GE="$HOME/.steam/root/compatibilitytools.d/GE-Proton7-55"
PREFIX="$GAMES_DIR/scghost-wine7-prefix"
CXBX_DIR="$REPO_ROOT/emulator"

if [ ! -f "$WT_GE/proton" ]; then
    echo "ERROR: GE-Proton7-55 not found. Run 04-setup-wine7.sh first."
    exit 1
fi
if [ ! -d "$PREFIX/pfx" ]; then
    echo "ERROR: Wine 7 prefix missing. Run 04-setup-wine7.sh first."
    exit 1
fi

export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT"
export STEAM_COMPAT_DATA_PATH="$PREFIX"
export PROTON_LOG=1
export PROTON_LOG_DIR="$REPO_ROOT/logs"

RENDERER="${RENDERER:-dxvk}"
if [ "$RENDERER" = "wine" ]; then
    export PROTON_USE_WINED3D=1
    echo "Renderer: wined3d (OpenGL)"
else
    echo "Renderer: DXVK (Vulkan)"
fi

if [ "$#" -ge 1 ] && [ "${1##*.}" = "xbe" ]; then
    case "$1" in
        /*) XBE_ABS="$1" ;;
        *)  XBE_ABS="$PWD/$1" ;;
    esac
    WINPATH="Z:${XBE_ABS//\//\\}"
    echo "Loading XBE: $WINPATH"
    cd "$CXBX_DIR"
    exec "$WT_GE/proton" run ./cxbx.exe "$WINPATH"
fi

echo "Opening Cxbx GUI"
cd "$CXBX_DIR"
exec "$WT_GE/proton" run ./cxbx.exe
