#!/bin/bash
# Show the tail of the latest recompiled runtime log.
#   scripts/17-show-log.sh [lines] [path]
set -u
ROOT=/home/agent/WORKSPACE-VM/projects/xbox-on-deb
LINES="${1:-200}"
LOG="${2:-}"
if [ -z "$LOG" ] && [ -e "$ROOT/logs/latest-runtime.log" ]; then
    LOG="$ROOT/logs/latest-runtime.log"
fi
if [ -z "$LOG" ]; then
    LOG="$ROOT/recomp/game/recomp_boot.log"
fi
if [ ! -f "$LOG" ]; then
    echo "no log yet at $LOG"
    exit 1
fi
echo "== $LOG =="
tail -n "$LINES" "$LOG"
