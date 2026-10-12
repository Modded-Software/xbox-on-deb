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
check uv           uv
check llvm-dlltool llvm
check perf         linux-tools-common
check wine         wine
check ffmpeg       ffmpeg
check pw-record    pipewire-bin
check gdbus        libglib2.0-bin

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

if [ "$missing" -ne 0 ]; then
    echo ""
    echo "install the missing system tools above (root) and re-run."
    exit 1
fi
echo "dependencies ready."