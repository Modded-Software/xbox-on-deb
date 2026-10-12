#!/bin/bash
set -euo pipefail

echo "=== [01] Creating StarCraft: Ghost GE-Proton prefix ==="

source "$PWD/scripts/config.env"
detect_ge_proton

if [ ! -d "$GAME_DATA_DIR" ]; then
    echo "ERROR: extracted game data not found at: $GAME_DATA_DIR"
    echo "Extract res/*.7z there first."
    exit 1
fi

mkdir -p "$SCGHOST_PREFIX"

# Create the prefix by running a harmless command through proton once.
if [ -d "$SCGHOST_PREFIX/pfx" ]; then
    echo "Prefix already exists: $SCGHOST_PREFIX"
else
    echo "Initializing prefix: $SCGHOST_PREFIX"
    export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT"
    export STEAM_COMPAT_DATA_PATH="$SCGHOST_PREFIX"
    "$GE_PROTON_DIR/proton" run cmd /c echo prefix-init
fi

echo ""
echo "=== [01] Complete ==="
echo "Prefix: $SCGHOST_PREFIX"
