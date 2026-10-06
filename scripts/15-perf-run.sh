#!/bin/bash
# Run the recompiled game for a fixed number of seconds and print the
# performance lines from the boot log, so a change can be measured in one
# command.
#
#   SECS=60 scripts/15-perf-run.sh          # keyboard+mouse, 60s
#   SECS=60 KBM=0 scripts/15-perf-run.sh    # controller path
#
# The [GPU-D3D11] counters are cumulative; compare the deltas between two
# consecutive reports, not the absolute numbers.
set -uo pipefail

ROOT=/home/agent/WORKSPACE-VM/projects/xbox-on-deb
SECS=${SECS:-60}
LOG="$ROOT/recomp/game/recomp_boot.log"
OUT="${OUT:-/tmp/opencode/perf-run.out}"

rm -f "$LOG"
echo "running for ${SECS}s (KBM=${KBM:-1})..."
( cd "$ROOT" && KBM="${KBM:-1}" timeout "$SECS" bash scripts/14-launch-recomp.sh ) >"$OUT" 2>&1
echo "run exit=$? (124 = reached the time limit)"

echo "--- frame rate ---"
grep -E "\[GPU\] presentation:" "$LOG"
echo "--- pipeline phases (cumulative) ---"
grep -E "\[GPU-D3D11\] time:|\[GPU-D3D11\] draw phases:|\[GPU\] flushes:" "$LOG"
