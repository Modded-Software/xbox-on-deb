#!/bin/bash
# Launch Cxbx with allow_ptrace.so preloaded so gdb can attach to the loader
# despite Yama ptrace_scope=1. Returns immediately (game runs in background).
#
# Usage: 11-launch-ptraceable.sh <xbe-path>
XBE="${1:-$PWD/extracted/StarCraft Ghost Xbox Finn Hillbilly/Ghost.xbe}"
source "$PWD/scripts/config.sh" || exit 1
detect_ge_proton
cd "$REPO_ROOT"

SO="$REPO_ROOT/tools/allow_ptrace.so"
if [[ ! -f "$SO" || "$REPO_ROOT/tools/allow_ptrace.c" -nt "$SO" ]]; then
    gcc -shared -fPIC -o "$SO" "$REPO_ROOT/tools/allow_ptrace.c" || {
        echo "failed to build $SO (is gcc installed?)" >&2
        exit 1
    }
fi
export LD_PRELOAD="$SO"
setsid bash scripts/03-launch-xbox-build.sh "$XBE" \
    > "$REPO_ROOT/logs/ptrace_launch.log" 2>&1 &
echo "launched (LD_PRELOAD=allow_ptrace.so); log: logs/ptrace_launch.log"
