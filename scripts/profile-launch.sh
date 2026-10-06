#!/bin/bash
# Launch Cxbx and profile the emulator process while it boots.
#
# Captures:
#   - perf.data (sampled stacks of cxbxr-ldr.exe, all threads)
#   - logs/dxvk/*  (DXVK debug log, includes pipeline creation)
#   - logs/prof_launch.log / KrnlDebug.txt / CxbxDebug.txt
#
# Usage: profile-launch.sh [duration-seconds]
#
# No `set -e`: wineserver -k and pgrep legitimately return non-zero when there
# is nothing to kill / nothing found, and we must continue either way.

DUR="${1:-180}"
source "$PWD/scripts/config.env"
detect_ge_proton
cd "$REPO_ROOT"

OUT="$REPO_ROOT/logs"
PERF_DATA="/tmp/opencode/perf.data"

echo "== killing previous session =="
WINEPREFIX="$SCGHOST_PREFIX/pfx" "$GE_PROTON_DIR/files/bin/wineserver" -k
sleep 3
for p in $(pgrep -f 'cxbx.exe|cxbxr-ldr.exe'); do
    kill -9 "$p"
done
sleep 2

rm -rf emulator/EmuDisk emulator/EmuMu emulator/EEPROM.bin \
       emulator/EmuMediaBoard emulator/ShaderCache emulator/SymbolCache
mkdir -p "$OUT/dxvk"
rm -f "$OUT/dxvk"/*.log

export DXVK_LOG_LEVEL=debug
export DXVK_LOG_PATH="$OUT/dxvk"

echo "== launching under profiling env =="
setsid bash scripts/03-launch-xbox-build.sh \
    "$REPO_ROOT/extracted/StarCraft Ghost Xbox Finn Hillbilly/Ghost.xbe" \
    > "$OUT/prof_launch.log" 2>&1 &

echo "== waiting for cxbxr-ldr.exe =="
pid=""
for _ in $(seq 1 90); do
    pid="$(pgrep -f 'cxbxr-ldr.exe')"
    if [ -n "$pid" ]; then
        break
    fi
    sleep 1
done
if [ -z "$pid" ]; then
    echo "ERROR: cxbxr-ldr.exe never appeared"
    exit 1
fi
echo "loader pid(s): $pid"

echo "== sampling for ${DUR}s (perf) =="
perf record -F 199 -g -p "$pid" -o "$PERF_DATA" -- sleep "$DUR" > "$OUT/perf_record.log" 2>&1

echo "== writing perf reports =="
perf report --stdio -i "$PERF_DATA" --sort comm,dso > "$OUT/perf_report.txt" 2>&1
perf report --stdio -i "$PERF_DATA" -g > "$OUT/perf_report_g.txt" 2>&1
perf script -i "$PERF_DATA" > "$OUT/perf_script.txt" 2>&1

echo "done. $PERF_DATA"
