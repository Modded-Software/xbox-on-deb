#!/bin/bash
set -euo pipefail

# Create a Wine 7.0 (GE-Proton7) prefix for Cxbx-Reloaded and install the
# runtime requirements from the Cxbx README (vcrun2019, d3dcompiler_47).

source "$PWD/scripts/config.env"

WT_GE="$HOME/.steam/root/compatibilitytools.d/GE-Proton7-55"
PREFIX="$GAMES_DIR/scghost-wine7-prefix"

if [ ! -f "$WT_GE/proton" ]; then
    echo "ERROR: GE-Proton7-55 not found at $WT_GE"
    exit 1
fi

mkdir -p "$PREFIX"

export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT"
export STEAM_COMPAT_DATA_PATH="$PREFIX"

if [ ! -d "$PREFIX/pfx" ]; then
    echo "Initializing Wine 7 prefix..."
    "$WT_GE/proton" run cmd /c echo wine7-prefix-init
fi

echo "Installing vcrun2019 + d3dcompiler_47 (native)..."
export WINEPREFIX="$PREFIX/pfx"
export PATH="$WT_GE/files/bin:$PATH"
winetricks -q --force vcrun2019 d3dcompiler_47

echo ""
echo "=== Wine 7 prefix ready: $PREFIX ==="
