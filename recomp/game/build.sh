#!/bin/bash
# Build the recompiled game (ghost.exe) for Windows x64 via the zig toolchain.
#
#   recomp/game/build.sh            # build
#   recomp/game/build.sh clean      # wipe build/
#   PROF=1 recomp/game/build.sh     # profiled build -> recomp/game/build-prof/
#
# PROF=1 builds a second exe whose every lifted function carries
# RECOMP_PROF_SCOPE (guest shadow call stack + time profiler, see
# refs/xboxrecomp/src/kernel/recomp_prof.h). It compiles an instrumented copy
# of src/recomp/gen made by recomp/tools/instrument_gen.py, so the normal
# build/ is untouched. Launch it with GHOST_BUILD=build-prof.
#
# Parallelism uses the machine's core count by default; override with JOBS=N.
set -euo pipefail

# Hardcoded: this sandbox resolves a script's own $0 through /proc, so
# dirname/readlink-based discovery lands in the wrong place.
ROOT="${REPO_ROOT:-$HOME/WORKSPACE-VM/projects/xbox-on-deb}"
BUILD="$ROOT/recomp/game/build"
JOBS="${JOBS:-$(nproc)}"

# Put the tracked hand-patches back into the generated tree. 20-regen-recomp.sh
# overwrites src/recomp/gen/* and takes every manual fix with it, so this runs
# before anything is configured -- and before the profiled copy is made, so
# PROF=1 builds the same code. Fails loudly if a patch no longer matches.
if [ "${1:-}" != "clean" ]; then
    bash "$ROOT/scripts/26-apply-game-patches.sh"
fi

CMAKE_EXTRA=()
if [ "${PROF:-0}" != "0" ]; then
    BUILD="$ROOT/recomp/game/build-prof"
    PROF_GEN="$ROOT/recomp/build/gen_prof"
    if [ "${1:-}" != "clean" ]; then
        "$ROOT/.venv-recomp/bin/python" "$ROOT/recomp/tools/instrument_gen.py" \
            --src "$ROOT/recomp/game/src/recomp/gen" --dst "$PROF_GEN"
    fi
    CMAKE_EXTRA+=(-DRECOMP_GEN_DIR="$PROF_GEN")
fi

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
        -DCMAKE_BUILD_TYPE=Release "${CMAKE_EXTRA[@]}"
fi

cmake --build "$BUILD" --target ghost -j "$JOBS"
echo "built $BUILD/ghost.exe"
