#!/bin/bash
# Measure how much data one run produces with a given logging configuration.
#
#   scripts/27-measure-logging.sh NAME [VAR=VALUE ...]
#   HOLD=120 scripts/27-measure-logging.sh NAME ...   # longer gameplay phase
#
# Two phases, because their rates differ by an order of magnitude:
#   boot     : the canonical user-path A-mash (boot -> menus -> first mission
#              -> gameplay; `run.py --user-state --only a-mash`),
#   gameplay : the game left running in the mission for HOLD seconds
#              (default 60; `run.py --hold`), which is the per-hour cost of a
#              long session.
# Reports, per phase, the runtime log's size, rate and per-tag breakdown
# (scripts/logstats.py); every other file the run created or grew (Proton log,
# kernel log, input recording, PCM capture, profile CSV, crash dumps, ...); the
# diary error counts and whether the test passed.
# Output: logs/measure/NAME.txt (also printed).
#
# Compare against a baseline run (NAME=baseline, no VARs): the delta is what
# the mechanism costs. Only runs from the same build compare.
set -u
ROOT="${REPO_ROOT:-$HOME/WORKSPACE-VM/projects/xbox-on-deb}"
cd "$ROOT"
source "$ROOT/scripts/config.sh" || exit 1

NAME="${1:?usage: 27-measure-logging.sh NAME [VAR=VALUE ...]}"
shift
HOLD="${HOLD:-60}"
OUTDIR="$ROOT/logs/measure"
mkdir -p "$OUTDIR"
OUT="$OUTDIR/$NAME.txt"
TOUT="$OUTDIR/$NAME.test.out"
MARK="$OUTDIR/.mark-$NAME"
DRIVE_C="$SCGHOST_PREFIX/pfx/drive_c"

bash scripts/16-stop-recomp.sh > "$OUTDIR/$NAME.stop.out" 2>&1
touch "$MARK"
START=$(date +%s)
env "$@" uv run python recomp/tests/run.py --user-state --only a-mash \
    --hold "$HOLD" > "$TOUT" 2>&1
END=$(date +%s)
bash scripts/16-stop-recomp.sh >> "$OUTDIR/$NAME.stop.out" 2>&1
SECS=$((END - START))

LOG=$(readlink -f "$ROOT/logs/latest-runtime.log")
HSTART=$(grep -o '\[HOLD\] start log_bytes=[0-9]*' "$TOUT" | grep -o '[0-9]*$')
HEND=$(grep -o '\[HOLD\] end log_bytes=[0-9]*' "$TOUT" | grep -o '[0-9]*$')
HSECS=$(grep -o '\[HOLD\] end .* secs=[0-9.]*' "$TOUT" | grep -o '[0-9.]*$')
{
    echo "== $NAME  env: $*"
    echo "date: $(date -Is)  wall: ${SECS}s  hold: ${HOLD}s"
    if grep -q '^  PASS ' "$TOUT"; then
        echo "test: PASS"
    else
        echo "test: FAIL (see $TOUT)"
    fi
    grep '^\[HOLD\]' "$TOUT"
    echo "-- whole run"
    uv run python scripts/logstats.py "$LOG" --secs "$SECS" --top 12 \
        --json "$OUTDIR/$NAME.json"
    if [ -n "$HSTART" ] && [ -n "$HEND" ]; then
        BSECS=$((SECS - ${HSECS%.*}))
        echo "-- boot phase (launch -> gameplay reached)"
        uv run python scripts/logstats.py "$LOG" --to "$HSTART" \
            --secs "$BSECS" --top 12
        echo "-- gameplay phase (hold)"
        uv run python scripts/logstats.py "$LOG" --from "$HSTART" \
            --to "$HEND" --secs "$HSECS" --top 12
    fi
    echo "-- files created/modified during the run (apparent bytes, on disk):"
    find "$ROOT/logs" "$DRIVE_C" "$ROOT/recomp/game" /tmp/opencode -maxdepth 2 \
        -type f -newer "$MARK" ! -path "$OUTDIR/*" ! -path "*/build*/*" \
        ! -path "/tmp/opencode/ask-claude*" ! -path "/tmp/opencode/dbgx/*" \
        -printf '%s\t%k KB\t%p\n'
} > "$OUT" 2>&1
rm -f "$MARK"
cat "$OUT"
