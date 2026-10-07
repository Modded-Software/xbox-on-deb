#!/bin/bash
# Regenerate the recompiled C from the XBE.
#
#   scripts/20-regen-recomp.sh [OUT_DIR]        # codegen only (fast, reuses analysis)
#   MODE=full scripts/20-regen-recomp.sh [OUT]  # disasm + func_id + abi + names, then codegen
#
# The generated tree (recomp/game/src/recomp/gen/) is gitignored because it is a
# build artifact: it is regenerated wholesale from Ghost.xbe. NEVER hand-patch a
# file under it -- edits there are lost on the next run. Put corrections in
# recomp/game/src/recomp_manual.c (recomp_lookup_manual), recomp/config/
# (seed_functions.json, annotations.csv), or recomp/tools/, all of which are
# tracked. `make gen-diff` regenerates into a fresh directory and diffs it
# against the in-tree tree so any hand edits are visible.
set -euo pipefail

# Hardcoded: this sandbox resolves a script's own $0 through /proc, so
# dirname/readlink-based discovery lands in the wrong place (see 18-launch-user.sh).
ROOT=/home/agent/WORKSPACE-VM/projects/xbox-on-deb
PY="$ROOT/.venv-recomp/bin/python"
XR="$ROOT/refs/xboxrecomp"
XBE="$ROOT/extracted/StarCraft Ghost Xbox Finn Hillbilly/Ghost.xbe"
B="$ROOT/recomp/build"
SEED="$ROOT/recomp/config/seed_functions.json"

MODE="${MODE:-codegen}"
OUT="${1:-$B/gen_fresh}"
# Resolve OUT to an absolute path now: we cd into $XR below, so a relative OUT
# would otherwise be created inside refs/xboxrecomp.
case "$OUT" in
    /*) ;;
    *) OUT="$ROOT/$OUT" ;;
esac

if [ ! -f "$XBE" ]; then
    echo "ERROR: XBE not found: $XBE" >&2
    exit 1
fi
if [ ! -d "$B/disasm" ] || [ ! -f "$B/disasm/functions.json" ]; then
    echo "ERROR: analysis missing ($B/disasm). Run MODE=full once." >&2
    exit 1
fi

cd "$XR"

if [ "$MODE" = "full" ]; then
    echo "== disasm (seeded) -> $B/disasm"
    "$PY" -m tools.disasm "$XBE" --analysis-json "$B/analysis.json" \
        --seed-functions "$SEED" -o "$B/disasm" -v --force
    echo "== func_id -> $B/func_id"
    "$PY" -m tools.func_id "$XBE" \
        --functions "$B/disasm/functions.json" --strings "$B/disasm/strings.json" \
        --xrefs "$B/disasm/xrefs.json" -o "$B/func_id"
    echo "== abi -> $B/abi"
    "$PY" -m tools.abi_analysis "$XBE" --functions "$B/disasm/functions.json" \
        --identified "$B/func_id/identified_functions.json" --output-dir "$B/abi"
    echo "== symbol map"
    "$PY" "$ROOT/recomp/tools/build_symbol_map.py"
    "$PY" "$ROOT/recomp/tools/apply_symbol_map.py" --no-backup
fi

echo "== codegen -> $OUT"
rm -rf "$OUT"
mkdir -p "$OUT"
"$PY" -m tools.recomp "$XBE" --all --split 250 \
    --functions "$B/disasm/functions.json" \
    --disasm-dir "$B/disasm" --func-id-dir "$B/func_id" --abi-dir "$B/abi" \
    --gen-dir "$OUT" -o "$OUT/recomp_all"
"$PY" "$ROOT/recomp/tools/annotate_gen.py" --gen-dir "$OUT" \
    --functions "$B/disasm/functions.json" --in-place
"$PY" "$ROOT/recomp/tools/group_by_source.py" --gen-dir "$OUT" \
    --functions "$B/disasm/functions.json" --out-dir "$OUT/gen_by_source"

echo "== done: $OUT"