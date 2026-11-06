#!/bin/bash
# Verify the Ubuntu build's xb_/kx_ replacement decorations against Ghost.map,
# using upstream GhostPC's checker. The checker's first argument is any symbol
# listing in the shape `\s[_@]xb_name@N\s`; `llvm-nm` on the built PE supplies
# that (lld does not emit an MSVC linker map).
set -euo pipefail
ROOT="${REPO_ROOT:-$HOME/WORKSPACE-VM/projects/xbox-on-deb}"
HERE="$ROOT/tools/ghostpc-ubuntu"
GAME="$ROOT/recomp/game/game"
MAP="$GAME/Ghost.map"
if [ ! -f "$MAP" ]; then
    echo "error: $MAP not found" >&2
    exit 1
fi
if [ ! -f "$HERE/build/GhostPC.exe" ]; then
    echo "error: build GhostPC.exe first (bash $HERE/build.sh)" >&2
    exit 1
fi
llvm-nm "$HERE"/build/obj/*.o > "$HERE/build/GhostPC.nm"
uv run python "$ROOT/refs/GhostPC/scripts/checkhooks.py" \
    "$HERE/build/GhostPC.nm" "$MAP"
