#!/bin/bash
# Patch cxbx.exe to remove WndMain::ResizeWindow's primary-monitor clamp, so
# Cxbx creates the configured VideoResolution window even when the primary
# monitor is smaller. The window can then be moved to the second monitor.
#
# Usage:
#   ./10-patch-cxbx-clamp.sh          # patch (backs up cxbx.exe.orig once)
#   ./10-patch-cxbx-clamp.sh restore  # restore from cxbx.exe.orig
set -euo pipefail

source "$PWD/scripts/config.env"

EXE="$REPO_ROOT/emulator/cxbx.exe"
BACKUP="$EXE.orig"

if [ "${1:-patch}" = "restore" ]; then
    if [ ! -f "$BACKUP" ]; then
        echo "ERROR: no backup at $BACKUP" >&2
        exit 1
    fi
    cp "$BACKUP" "$EXE"
    echo "restored $EXE from $BACKUP"
    exit 0
fi

if [ ! -f "$EXE" ]; then
    echo "ERROR: $EXE not found" >&2
    exit 1
fi

/usr/bin/python3 "$REPO_ROOT/scripts/patch_cxbx_clamp.py" "$EXE"
