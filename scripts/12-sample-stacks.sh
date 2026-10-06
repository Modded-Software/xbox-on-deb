#!/bin/bash
# Sample all thread backtraces of a running Wine/Cxbx process.
#
# Requires the process to have allow_ptrace.so preloaded (see
# 11-launch-ptraceable.sh). gdb stops the process briefly and detaches.
#
# Usage: 12-sample-stacks.sh <pid> [label]
PID="${1:?usage: 12-sample-stacks.sh <pid> [label]}"
LABEL="${2:-sample}"
OUT="$PWD/logs/stacks_${LABEL}.txt"
gdb -p "$PID" -batch \
    -ex 'set pagination off' \
    -ex 'set print frame-arguments none' \
    -ex 'thread apply all bt' \
    > "$OUT" 2>&1
echo "wrote $OUT"
