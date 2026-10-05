#!/bin/bash
# set-audio-buffer.sh <streamAhead-ms>
#
# Tune Cxbx's emulated-DirectSound streaming depth by patching the compile-time
# default of g_dsBufferStreaming.streamAhead inside cxbxr-emu.dll. This global
# backs the in-game F1 -> "DSBuffer Visualization" -> "Buffering Controls"
# slider; there is no settings.ini key for it.
#
# Struct layout at the located site: DWORD streamInterval=1, DWORD streamAhead=50,
# float tweakCopyOffset=0. We only overwrite streamAhead.
#
# The original DLL is preserved next to it as cxbxr-emu.dll.orig and reused as
# the patch source so re-running with a new value is idempotent.

set -euo pipefail

MS="${1:-250}"

source "$PWD/scripts/config.env"
DLL="$REPO_ROOT/emulator/cxbxr-emu.dll"
BACKUP="$DLL.orig"
OFF=$((0x69fb18 + 4))   # streamAhead field; site = 0x69fb18

if [ ! -f "$DLL" ]; then
    echo "ERROR: $DLL not found"
    exit 1
fi
if [ ! -f "$BACKUP" ]; then
    cp "$DLL" "$BACKUP"
    echo "Backed up original -> $BACKUP"
fi

verify_site() {
    # first DWORD of the struct must be streamInterval == 1
    local interval
    interval="$(od -An -tu4 -j "$((OFF - 4))" -N 4 "$BACKUP")"
    interval="${interval// /}"
    if [ "$interval" != "1" ]; then
        echo "ERROR: unexpected struct at 0x69fb18 (interval=$interval). DLL changed?"
        exit 1
    fi
}

write_default() {
    local ms="$1" b0 b1 b2 b3 tmp
    b0=$((ms & 255)); b1=$(((ms >> 8) & 255))
    b2=$(((ms >> 16) & 255)); b3=$(((ms >> 24) & 255))
    tmp="$(mktemp)"
    printf "$(printf '\\x%02x\\x%02x\\x%02x\\x%02x' "$b0" "$b1" "$b2" "$b3")" > "$tmp"
    dd if="$tmp" of="$DLL" bs=1 seek="$OFF" count=4 conv=notrunc status=none
    rm -f "$tmp"
}

verify_site
old="$(od -An -tu4 -j "$OFF" -N 4 "$BACKUP")"
old="${old// /}"
write_default "$MS"
new="$(od -An -tu4 -j "$OFF" -N 4 "$DLL")"
new="${new// /}"
if [ "$new" != "$MS" ]; then
    echo "ERROR: patch verification failed (wrote $MS, read $new)"
    exit 1
fi
echo "streamAhead: $old ms -> $new ms  ($DLL)"
