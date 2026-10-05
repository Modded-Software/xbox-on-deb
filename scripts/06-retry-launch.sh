#!/bin/bash
# Bounded retry launcher for Cxbx-Reloaded.
#
# The Cxbx XBE load is flaky under Wine (see upstream issue #1897): a launch
# either reaches "ResetSwapChain" (a 640x480 render window is created) or dies
# during kernel init. Retrying from a clean emulated-media state usually gets
# through. This script automates that and reports the success rate.
#
# Usage: 06-retry-launch.sh <xbe-path> [max-attempts] [seconds-per-attempt]

XBE="${1:?usage: 06-retry-launch.sh <xbe> [max] [wait]}"
MAX="${2:-6}"
WAIT="${3:-45}"

source "$PWD/scripts/config.env"
detect_ge_proton
cd "$REPO_ROOT"

kill_session() {
    WINEPREFIX="$SCGHOST_PREFIX/pfx" "$GE_PROTON_DIR/files/bin/wineserver" -k
    sleep 3
    local p
    for p in $(pgrep -f 'cxbx.exe|cxbxr-ldr.exe'); do
        kill -9 "$p"
    done
    sleep 2
}

marker="ResetSwapChain"
attempt=1
while [ "$attempt" -le "$MAX" ]; do
    echo "=== attempt $attempt/$MAX ==="
    kill_session
    rm -rf emulator/EmuDisk emulator/EmuMu emulator/EEPROM.bin \
           emulator/EmuMediaBoard emulator/ShaderCache emulator/SymbolCache
    LOG="$REPO_ROOT/logs/cxbx_retry_$attempt.log"
    setsid bash scripts/03-launch-xbox-build.sh "$XBE" > "$LOG" 2>&1 &
    sleep "$WAIT"
    if grep -q "$marker" "$LOG"; then
        echo "SUCCESS on attempt $attempt (render swapchain created)"
        echo "log: $LOG"
        exit 0
    fi
    echo "attempt $attempt: no swapchain"
    attempt=$((attempt + 1))
done
echo "FAILED after $MAX attempts"
exit 1
