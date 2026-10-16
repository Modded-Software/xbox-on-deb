#!/bin/bash
# Install this project's dependencies.
#
#   bash scripts/00-install-deps.sh        # or: make install
#
# Three groups:
#   1. system tools - checked, not installed: this box has no passwordless
#      root, so a missing entry prints the package to install by hand.
#   2. Python environments - the project env (pyproject.toml + uv.lock, the
#      gamepad proxy) and the recomp pipeline env (.venv-recomp: capstone,
#      pefile, and ziglang, which backs the cross-compiler wrappers).
#   3. the recompilation toolkit clone (refs/xboxrecomp).
#
# GE-Proton and the game data are not distributable: windows-on-deb scripts
# 01-03 install GE-Proton, and you supply the extracted XBE yourself.
set -eu

# Hardcoded: this sandbox resolves a script's own $0 through /proc, so
# dirname/readlink-based discovery lands in the wrong place (see build.sh).
ROOT="${REPO_ROOT:-$HOME/WORKSPACE-VM/projects/xbox-on-deb}"
source "$ROOT/scripts/config.sh" || exit 1

echo "== system tools =="
missing=0
check() {   # check <binary> <package>
    local _path
    if _path="$(command -v "$1")"; then
        printf '  ok       %-12s %s\n' "$1" "$_path"
    else
        printf '  MISSING  %-12s install: %s\n' "$1" "$2"
        missing=1
    fi
}
check git          git
check make         make
check cmake        cmake
check pkg-config   pkg-config
check uv           uv
check llvm-dlltool llvm
check perf         linux-tools-common
check wine         wine
check ffmpeg       ffmpeg
check pw-record    pipewire-bin
check gdbus        libglib2.0-bin

# Native Linux build of the toolkit's runtime libraries (its OpenGL backend:
# src/d3d/CMakeLists.txt find_package(SDL2) + pkg epoxy, src/kernel OpenSSL,
# src/video ffmpeg). The game itself is cross-compiled for Windows via zig, so
# WIN32 is set and none of these are configured - they are NOT needed for the
# active path, only for building/testing the toolkit natively on Linux. Reported
# without failing; to install, run refs/xboxrecomp/tools/linux/install_deps.sh.
echo "== toolkit native Linux build (optional) =="
optional_missing=0
check_opt_pkg() {   # check_opt_pkg <pkg-config name> <package>
    if pkg-config --exists "$1"; then
        printf '  ok       %-12s %s\n' "$1" "$(pkg-config --modversion "$1")"
    else
        printf '  MISSING  %-12s install: %s\n' "$1" "$2"
        optional_missing=1
    fi
}
check_opt_pkg sdl2         libsdl2-dev
check_opt_pkg epoxy        libepoxy-dev
check_opt_pkg openssl      libssl-dev
check_opt_pkg libavcodec   libavcodec-dev
check_opt_pkg libavformat  libavformat-dev
check_opt_pkg libavutil    libavutil-dev
check_opt_pkg libswscale   libswscale-dev

echo "== Python environments =="
uv sync --project "$ROOT"
if [ ! -x "$ROOT/.venv-recomp/bin/python" ]; then
    uv venv "$ROOT/.venv-recomp"
fi
uv pip install --python "$ROOT/.venv-recomp/bin/python" capstone pefile ziglang

echo "== recompilation toolkit =="
if [ -d "$ROOT/refs/xboxrecomp/.git" ]; then
    echo "  ok       refs/xboxrecomp @ $(git -C "$ROOT/refs/xboxrecomp" rev-parse --short HEAD) (update with: make toolkit)"
else
    bash "$ROOT/scripts/19-setup-toolkit.sh"
fi

echo "== external, not fetchable here =="
if ! find_ge_proton; then
    echo "  MISSING  GE-Proton in $COMPAT_TOOLS_DIR (run windows-on-deb 01-03)"
fi
if [ ! -d "$GAME_DATA_DIR" ]; then
    echo "  MISSING  game data at $GAME_DATA_DIR (supply the extracted XBE)"
fi

if [ "$optional_missing" -ne 0 ]; then
    echo ""
    echo "note: the toolkit's native Linux build needs the packages above; the"
    echo "      game cross-build (the active path) does not. Install them with:"
    echo "        bash refs/xboxrecomp/tools/linux/install_deps.sh"
fi

if [ "$missing" -ne 0 ]; then
    echo ""
    echo "install the missing system tools above (root) and re-run."
    exit 1
fi
echo "dependencies ready."