#!/bin/bash
# Launch Cxbx with allow_ptrace.so preloaded so gdb can attach to the loader
# despite Yama ptrace_scope=1. Returns immediately (game runs in background).
#
# Usage: 11-launch-ptraceable.sh <xbe-path>
XBE="${1:-$PWD/extracted/StarCraft Ghost Xbox Finn Hillbilly/Ghost.xbe}"
source "$PWD/scripts/config.env"
detect_ge_proton
cd "$REPO_ROOT"

export LD_PRELOAD="$REPO_ROOT/tools/allow_ptrace.so"
setsid bash scripts/03-launch-xbox-build.sh "$XBE" \
    > "$REPO_ROOT/logs/ptrace_launch.log" 2>&1 &
echo "launched (LD_PRELOAD=allow_ptrace.so); log: logs/ptrace_launch.log"
