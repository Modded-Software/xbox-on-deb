#!/bin/bash
# Kill the current Cxbx/Proton session for this prefix.
cd "${REPO_ROOT:-$HOME/WORKSPACE-VM/projects/xbox-on-deb}"
source "$PWD/scripts/config.sh" || exit 1
detect_ge_proton
WINEPREFIX="$SCGHOST_PREFIX/pfx" "$GE_PROTON_DIR/files/bin/wineserver" -k
sleep 3
for p in $(pgrep -f 'cxbx.exe|cxbxr-ldr.exe'); do
    kill -9 "$p"
done
sleep 2
echo "remaining:"
pgrep -af 'cxbxr-ldr.exe'
