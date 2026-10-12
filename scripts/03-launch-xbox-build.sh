#!/bin/bash
set -euo pipefail

# Launch Cxbx-Reloaded under GE-Proton.
#
# Usage:
#   03-launch-xbox-build.sh gui                  # open the Cxbx GUI
#   03-launch-xbox-build.sh /path/to/Game.xbe    # load an XBE directly (loader)
#
# Environment:
#   RENDERER=dxvk (default, D3D9->DXVK/Vulkan) | RENDERER=wine (OpenGL/wined3d)

source "$PWD/scripts/config.env"
detect_ge_proton

CXBX_DIR="$REPO_ROOT/emulator"
if [ ! -f "$CXBX_DIR/cxbx.exe" ]; then
    echo "ERROR: Cxbx not found in $CXBX_DIR"
    exit 1
fi

if [ ! -d "$SCGHOST_PREFIX/pfx" ]; then
    echo "ERROR: prefix not found. Run 01-setup-prefix.sh first."
    exit 1
fi

export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT"
export STEAM_COMPAT_DATA_PATH="$SCGHOST_PREFIX"
export PROTON_USE_NTSYNC=1
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
    exec "$GE_PROTON_DIR/proton" run ./cxbx.exe "$WINPATH"
fi

echo "Opening Cxbx GUI"
cd "$CXBX_DIR"
exec "$GE_PROTON_DIR/proton" run ./cxbx.exe
