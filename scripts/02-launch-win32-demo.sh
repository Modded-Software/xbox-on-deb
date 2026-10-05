#!/bin/bash
set -euo pipefail

# Launch a Win32 StarCraft: Ghost demo executable (Star*.exe) via GE-Proton.
#
# Usage: 02-launch-win32-demo.sh [Star_u.exe|Star.exe|Star_d.exe] [extra args...]
#
# Environment:
#   RENDERER=dxvk  (default, Vulkan via DXVK d3d8)  or  RENDERER=wine (OpenGL/wined3d)
#   HUD=1          show DXVK HUD overlay

source "$PWD/scripts/config.env"
detect_ge_proton

EXE="${1:-Star_u.exe}"
if [ "$#" -gt 0 ]; then
    shift
fi

if [ ! -f "$GAME_DATA_DIR/$EXE" ]; then
    echo "ERROR: $EXE not found in $GAME_DATA_DIR"
    exit 1
fi

if [ ! -d "$SCGHOST_PREFIX/pfx" ]; then
    echo "ERROR: prefix not found. Run 01-setup-prefix.sh first."
    exit 1
fi

RENDERER="${RENDERER:-dxvk}"

export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT"
export STEAM_COMPAT_DATA_PATH="$SCGHOST_PREFIX"
export PROTON_USE_NTSYNC=1
export PROTON_LOG=1
export PROTON_LOG_DIR="$REPO_ROOT/logs"

mkdir -p "$PROTON_LOG_DIR"

if [ "$RENDERER" = "wine" ]; then
    export PROTON_USE_WINED3D=1
    echo "Renderer: wined3d (OpenGL)"
else
    export DXVK_HUD="${HUD:-0}"
    echo "Renderer: DXVK (Vulkan)"
fi

cd "$GAME_DATA_DIR"
echo "Working dir: $PWD"
echo "Launching:   $EXE $*"
echo "Logs:        $PROTON_LOG_DIR"
echo ""

exec "$GE_PROTON_DIR/proton" run "./$EXE" "$@"
