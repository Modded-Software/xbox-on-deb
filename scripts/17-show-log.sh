#!/bin/bash
# Show the tail of the recompiled runtime's log.
set -u
LOG=/home/agent/WORKSPACE-VM/projects/xbox-on-deb/recomp/game/recomp_boot.log
LINES="${1:-200}"
if [ ! -f "$LOG" ]; then
    echo "no log yet at $LOG"
    exit 1
fi
tail -n "$LINES" "$LOG"
