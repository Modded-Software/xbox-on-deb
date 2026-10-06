#!/bin/bash
# Launch the recompiled game for hands-on testing.
#
# Self-contained: stops any stale instance, then starts a fresh one, so a
# launch never stacks and never depends on a preceding stop. setsid puts the
# game in its own session, so it survives the command that started it.
#
# The runtime log is timestamped (RECOMP_LOG) so a bad run is kept, and
# RECOMP_VBLANK=1 delivers the GPU vertical blank the title's D3D8 library
# waits on (without it the post-FMV overlay handshake can stall).
set -u
ROOT=/home/agent/WORKSPACE-VM/projects/xbox-on-deb
cd "$ROOT"
mkdir -p logs

# stop any stale instance (wineserver -k covers the whole prefix)
bash scripts/16-stop-recomp.sh

TS=$(date +%Y%m%d-%H%M%S)
RUNLOG="$ROOT/logs/runtime-$TS.log"
ln -sf "runtime-$TS.log" "$ROOT/logs/latest-runtime.log"

KBM=1 DIAG=1 RECOMP_VBLANK=1 RECOMP_LOG="$RUNLOG" \
    RECOMP_WATCHDOG_SECS=15 RECOMP_WATCHDOG_REPEAT=1 \
    setsid bash scripts/14-launch-recomp.sh > logs/launch.out 2>&1 &

echo "launched; window title is 'StarCraft: Ghost'"
echo "  runtime log : logs/runtime-$TS.log  (logs/latest-runtime.log)"
echo "  launcher log: logs/launch.out"
echo "  vblank      : on (RECOMP_VBLANK=1)"
echo "  stop with   : make stop"
