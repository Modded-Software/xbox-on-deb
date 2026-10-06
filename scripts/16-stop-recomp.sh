#!/bin/bash
# Stop any running recompiled game and its wineserver.
#
# wineserver -k tears down every process in this prefix, which is the whole
# game. A by-name sweep of ghost.exe is not used: the host guard rejects it.
set -u
ROOT=/home/agent/WORKSPACE-VM/projects/xbox-on-deb
cd "$ROOT"
source "$PWD/scripts/config.env"
detect_ge_proton

WINEPREFIX="$SCGHOST_PREFIX/pfx" "$GE_PROTON_DIR/files/bin/wineserver" -k
sleep 3
echo "remaining:"
pgrep -af "/ghost.exe"
echo "(done)"
