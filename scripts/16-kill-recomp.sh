#!/bin/bash
# Stop any running recompiled game and its wineserver.
set -u
ROOT=/home/agent/WORKSPACE-VM/projects/xbox-on-deb
cd "$ROOT"
source "$PWD/scripts/config.env"
detect_ge_proton

for p in $(pgrep -f "/ghost.exe"); do
    kill -9 "$p"
done
WINEPREFIX="$SCGHOST_PREFIX/pfx" "$GE_PROTON_DIR/files/bin/wineserver" -k
sleep 2
echo "remaining:"
pgrep -af "/ghost.exe"
