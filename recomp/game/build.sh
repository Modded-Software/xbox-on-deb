#!/bin/bash
# Build the recompiled game (ghost.exe) for Windows x64 via the zig toolchain.
#
#   recomp/game/build.sh            # build
#   recomp/game/build.sh clean      # wipe build/
#
# Parallelism defaults to the machine's core count; override with JOBS=N.
set -euo pipefail

# Hardcoded: this sandbox resolves a script's own $0 through /proc, so
# dirname/readlink-based discovery lands in the wrong place.
ROOT=/home/agent/WORKSPACE-VM/projects/xbox-on-deb
BUILD="$ROOT/recomp/game/build"
JOBS="${JOBS:-$(nproc)}"

if [ "${1:-}" = "clean" ]; then
    rm -rf "$BUILD"
    echo "removed $BUILD"
    exit 0
fi

# The import libs the toolkit links by their SDK name are generated artifacts
# (gitignored). Rebuild them if missing so a fresh clone links.
if [ ! -f "$ROOT/recomp/toolchain/lib/libd3dcompiler.a" ]; then
    bash "$ROOT/recomp/toolchain/make_import_libs.sh"
fi

if [ ! -f "$BUILD/CMakeCache.txt" ]; then
    cmake -S "$ROOT/recomp/game" -B "$BUILD" -G "Unix Makefiles" \
        -DCMAKE_TOOLCHAIN_FILE="$ROOT/recomp/toolchain/zig-windows-x64.cmake" \
        -DCMAKE_BUILD_TYPE=Release
fi

cmake --build "$BUILD" --target ghost -j "$JOBS"
echo "built $BUILD/ghost.exe"
