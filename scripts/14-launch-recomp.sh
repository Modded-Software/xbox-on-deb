#!/bin/bash
set -euo pipefail

# Launch the statically recompiled StarCraft: Ghost (ghost.exe) under GE-Proton.
#
#   scripts/14-launch-recomp.sh              # normal run
#   RENDERER=wine scripts/14-launch-recomp.sh  # wined3d instead of DXVK
#
# The recompiled exe is plain Windows x64; it loads game\Ghost.xbe by relative
# path, so the working directory must be recomp/game (where game/ resolves).

source "$PWD/scripts/config.env"
detect_ge_proton

GAME_DIR="$REPO_ROOT/recomp/game"
EXE="$GAME_DIR/build/ghost.exe"

if [ ! -f "$EXE" ]; then
    echo "ERROR: $EXE not found. Build it first:"
    echo "  cmake -S recomp/game -B recomp/game/build \\"
    echo "        -DCMAKE_TOOLCHAIN_FILE=\"\$PWD/recomp/toolchain/zig-windows-x64.cmake\""
    echo "  cmake --build recomp/game/build --target ghost -j 32"
    exit 1
fi

if [ ! -d "$SCGHOST_PREFIX/pfx" ]; then
    echo "ERROR: prefix not found. Run 01-setup-prefix.sh first."
    exit 1
fi

export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT"
export STEAM_COMPAT_DATA_PATH="$SCGHOST_PREFIX"
export PROTON_USE_NTSYNC=1
export PROTON_LOG=1
export PROTON_LOG_DIR="$REPO_ROOT/logs"

if [ "${RENDERER:-dxvk}" = "wine" ]; then
    export PROTON_USE_WINED3D=1
    echo "Renderer: wined3d (OpenGL)"
else
    echo "Renderer: DXVK (Vulkan)"
fi

# Bring-up diagnostics (xboxrecomp runtime reads these):
#   RECOMP_UNIMPL_TRAP=1   abort at the first untranslated instruction
#   RECOMP_WATCHDOG_SECS=N report a hang from slowness after N seconds
#   RECOMP_AC97_READY=1    bring up the emulated APU
export RECOMP_AC97_READY="${RECOMP_AC97_READY:-1}"

cd "$GAME_DIR"
exec "$GE_PROTON_DIR/proton" run ./build/ghost.exe
