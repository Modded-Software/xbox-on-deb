#!/bin/bash
# Launch the recompiled game for hands-on testing.
#
# The default environment matches what recomp/tests/framework.py launches with
# (which reaches the menu and a mission reliably): keyboard+mouse, input
# diagnostics, and each run's own timestamped log. The repeating watchdog is
# NOT enabled by default -- it suspends the guest thread every interval to
# sample its RIP, which can wedge a load -- and neither is the vblank
# override. Both are opt-in via WATCH=1 / VBLANK=1 for diagnosis.
#
# setsid puts the game in its own session, so it survives the command that
# started it.
set -u
ROOT=/home/agent/WORKSPACE-VM/projects/xbox-on-deb
cd "$ROOT"
mkdir -p logs

# stop any stale instance (wineserver -k covers the whole prefix)
bash scripts/16-stop-recomp.sh

TS=$(date +%Y%m%d-%H%M%S)
RUNLOG="$ROOT/logs/runtime-$TS.log"
ln -sf "runtime-$TS.log" "$ROOT/logs/latest-runtime.log"

EXTRA=""
if [ "${WATCH:-0}" != "0" ]; then
    EXTRA="$EXTRA RECOMP_WATCHDOG_SECS=15 RECOMP_WATCHDOG_REPEAT=1"
fi
if [ "${VBLANK:-0}" != "0" ]; then
    EXTRA="$EXTRA RECOMP_VBLANK=1"
fi

env KBM=1 DIAG=1 RECOMP_LOG="$RUNLOG" $EXTRA \
    setsid bash scripts/14-launch-recomp.sh > logs/launch.out 2>&1 &

echo "launched; window title is 'StarCraft: Ghost'"
echo "  runtime log : logs/runtime-$TS.log  (logs/latest-runtime.log)"
echo "  launcher log: logs/launch.out"
echo "  watchdog    : ${WATCH:-0}   vblank: ${VBLANK:-0}"
echo "  stop with   : make stop"
