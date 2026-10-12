#!/bin/bash
# Paired A/B performance run: alternate control and variant runs of the
# in-game framerate test (recomp/tests/test_performance.py, user state, window
# minimised) and summarise each run's FPS median, the async-flip / readback
# counters, and the error counts from its runtime log.
#
#   scripts/22-ab-perf.sh RECOMP_ASYNC_FLIP=0            # control vs variant, 2 pairs
#   PAIRS=3 scripts/22-ab-perf.sh RECOMP_ASYNC_FLIP=0
#   scripts/22-ab-perf.sh                                # control only (baseline)
#
# The control runs with the ambient environment; the variant adds VAR=VAL.
# Summary: logs/ab-perf-<timestamp>.txt (also printed). Scene drift between
# launches is large, so only compare runs from the same invocation.
set -uo pipefail

ROOT="${REPO_ROOT:-$HOME/WORKSPACE-VM/projects/xbox-on-deb}"
cd "$ROOT"
PAIRS=${PAIRS:-2}
VARIANT=${1:-}
OUT="logs/ab-perf-$(date +%Y%m%d-%H%M%S).txt"

run_one() {
    local label=$1; shift          # remaining args: VAR=VAL assignments (none = control)
    bash scripts/16-stop-recomp.sh >> logs/ab-perf-stop.out 2>&1
    env "$@" RECOMP_KICK_STATS=1 RECOMP_NV2A_GPU_TIMING=1 \
        uv run python recomp/tests/run.py --user-state --only performance \
        > "logs/ab-perf-$label.out" 2>&1
    local log counters
    log=$(readlink -f logs/latest-runtime.log)
    # Counters are cumulative: keep only the last report of each kind.
    mapfile -t counters < <(grep "\[GPU-D3D11\] async flip:\|\[GPU-D3D11\] completion:\|\[GPU-D3D11\] readback:" "$log")
    {
        echo "== $label ${*:-(control)}  $log"
        grep "median\|FAIL" "logs/ab-perf-$label.out"
        printf '  %s\n' "${counters[@]: -3}"
        echo "  desync/STALLDUMP/CRASH: $(grep -c "desync\|STALLDUMP\|\[CRASH\]" "$log")"
    } | tee -a "$OUT"
    local rc=${PIPESTATUS[0]}
    if [ "$rc" -ne 0 ]; then
        echo "ab-perf: summary write failed (rc=$rc)" >&2
        exit "$rc"
    fi
}

for pair in $(seq 1 "$PAIRS"); do
    run_one "control$pair"
    if [ -n "$VARIANT" ]; then
        run_one "variant$pair" "$VARIANT"
    fi
done
bash scripts/16-stop-recomp.sh >> logs/ab-perf-stop.out 2>&1
echo "summary: $OUT"
