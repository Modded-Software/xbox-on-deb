#!/bin/bash
# Launch the recompiled game for hands-on testing.
#
# Detached (setsid) so it survives the shell that started it. Keyboard+mouse
# is on, and the repeating watchdog is armed so that if the game deadlocks the
# last [WATCHDOG] sample in recomp/game/recomp_boot.log names where it stuck.
set -u
ROOT=/home/agent/WORKSPACE-VM/projects/xbox-on-deb
cd "$ROOT"
mkdir -p logs

KBM=1 DIAG=1 RECOMP_WATCHDOG_SECS=15 RECOMP_WATCHDOG_REPEAT=1 \
    setsid bash scripts/14-launch-recomp.sh > logs/launch.out 2>&1 &

echo "launched; window title is 'StarCraft: Ghost'"
echo "  runtime log : recomp/game/recomp_boot.log"
echo "  launcher log: logs/launch.out"
echo "  stop with   : make kill"
