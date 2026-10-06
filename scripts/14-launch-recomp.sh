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

# Keyboard: stop Wine from talking to the X11 input method (IBus/XIM).
#
# Proton 9+ (and GE-Proton 11, which we use) turned XIM back on by default.
# When it is on, Wine routes key events through IBus, which replays them one at
# a time; the press, the auto-repeats and the final release back up by seconds
# (tens of seconds under load), so a key looks unregistered and then fires long
# afterwards. This is the long-standing ibus/Wine bug
# (ValveSoftware/Proton#5294), not our code, and it is invisible to XTest (the
# test framework injects straight into the X server, past the IM), which is why
# automated input works while a real keyboard does not.
#
# PROTON_NO_XIM / WINE_ALLOW_XIM are Proton's switches, but they are not enough
# on every build: tell the X client library itself to use no input method, so
# there is nothing to connect to. XMODIFIERS=@im=none is the definitive one;
# the rest cover GTK/Qt/CLI IM frontends.
export PROTON_NO_XIM=1
export WINE_ALLOW_XIM=0
export XMODIFIERS="@im=none"
export GTK_IM_MODULE=""
export QT_IM_MODULE=""
export XIM=""
export XIM_PROGRAM=""

# Bring-up diagnostics (xboxrecomp runtime reads these):
#   RECOMP_UNIMPL_TRAP=1   abort at the first untranslated instruction
#   RECOMP_WATCHDOG_SECS=N report a hang from slowness after N seconds
#   RECOMP_AC97_READY=1    bring up the emulated APU
export RECOMP_AC97_READY="${RECOMP_AC97_READY:-1}"

cd "$GAME_DIR"

# KBM=1 launches with keyboard+mouse control (--kbm). The exe sets RECOMP_KBM
# itself from the flag; nothing else needs to know.
ARGS=()
if [ "${KBM:-0}" != "0" ]; then
    ARGS+=(--kbm)
    echo "Input: keyboard + mouse (--kbm)"
else
    echo "Input: Xbox controller (XInput)"
fi

# DIAG=1 prints the input chain once a second to the boot log.
if [ "${DIAG:-0}" != "0" ]; then
    export RECOMP_INPUT_DIAG=1
    echo "Input diagnostic: on"
fi

exec "$GE_PROTON_DIR/proton" run ./build/ghost.exe "${ARGS[@]}"
