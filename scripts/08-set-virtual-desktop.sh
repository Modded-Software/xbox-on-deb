#!/bin/bash
# set-virtual-desktop.sh [on|off] [WxH]
#
# Cxbx sizes its render window from the primary monitor's dimensions. When the
# primary display is a rotated/portrait panel narrower than the requested
# resolution, the window (and thus the DXVK swapchain) gets clamped to a square
# and the game image is distorted. A Wine virtual desktop pins the reported
# screen metrics to a fixed 16:9 size, independent of the physical panel.
#
# Usage: 08-set-virtual-desktop.sh on 1920x1080
#        08-set-virtual-desktop.sh off

set -euo pipefail

MODE="${1:-on}"
SIZE="${2:-1920x1080}"

source "$PWD/scripts/config.env"
detect_ge_proton

export WINEPREFIX="$SCGHOST_PREFIX/pfx"
WINE="$GE_PROTON_DIR/files/bin/wine"

case "$MODE" in
    on)
        "$WINE" reg add 'HKCU\Software\Wine\Explorer' /v Desktop /d 'Default' /f
        "$WINE" reg add 'HKCU\Software\Wine\Explorer\Desktops' /v Default /d "$SIZE" /f
        echo "Wine virtual desktop enabled at $SIZE"
        ;;
    off)
        set +e
        "$WINE" reg delete 'HKCU\Software\Wine\Explorer' /v Desktop /f
        "$WINE" reg delete 'HKCU\Software\Wine\Explorer\Desktops' /v Default /f
        set -e
        echo "Wine virtual desktop disabled"
        ;;
    *)
        echo "usage: 08-set-virtual-desktop.sh [on|off] [WxH]"
        exit 1
        ;;
esac
