#!/bin/bash
# Prepare a GhostPC game directory and launch it under GE-Proton.
#
#   bash tools/ghostpc-ubuntu/run-wine.sh            # build if needed, then run
#   RENDERER=wine bash tools/ghostpc-ubuntu/run-wine.sh
#
# GhostPC loads Ghost.exe + Ghost.map from its own directory, so this creates
# run/ with the built exe and symlinks to the game data in recomp/game/game.
set -euo pipefail

ROOT="${REPO_ROOT:-$HOME/WORKSPACE-VM/projects/xbox-on-deb}"
HERE="$ROOT/tools/ghostpc-ubuntu"
BUILD="$HERE/build"
RUN="$HERE/run"
GAME="$ROOT/recomp/game/game"
source "$ROOT/scripts/config.sh" || exit 1

if [ ! -f "$BUILD/GhostPC.exe" ]; then
    echo "GhostPC.exe not built; building..."
    bash "$HERE/build.sh"
fi
if [ ! -f "$GAME/Ghost.exe" ]; then
    echo "error: $GAME/Ghost.exe not found" >&2
    exit 1
fi

detect_ge_proton
# GHOSTPC_GE_PROTON=<dir name> picks a specific tool (e.g. GE-Proton7-55).
# GE-Proton11-1's DXVK 2.7 dev build hits VK_ERROR_DEVICE_LOST on Intel DG2
# (Mesa 25.2.8, i915); GE-Proton7-55 with DXVK 2.1 runs.
if [ -n "${GHOSTPC_GE_PROTON:-}" ] && [ -x "$COMPAT_TOOLS_DIR/$GHOSTPC_GE_PROTON/proton" ]; then
    GE_PROTON_DIR="$COMPAT_TOOLS_DIR/$GHOSTPC_GE_PROTON"
fi

mkdir -p "$RUN" "$ROOT/logs"
cp -f "$BUILD/GhostPC.exe" "$RUN/GhostPC.exe"
if [ -f "$GAME/Ghost.map" ] && [ ! -e "$RUN/Ghost.map" ]; then
    ln -s "$GAME/Ghost.map" "$RUN/Ghost.map"
fi
for entry in "$GAME"/*; do
    base=$(basename "$entry")
    case "$base" in
        Ghost.exe|Ghost.map|GhostPC.exe|ghostpc.log|ghostpc.prev.log|save) continue ;;
    esac
    if [ ! -e "$RUN/$base" ]; then
        ln -s "$entry" "$RUN/$base"
    fi
done
if [ ! -e "$RUN/Ghost.exe" ]; then
    ln -s "$GAME/Ghost.exe" "$RUN/Ghost.exe"
fi

# Keyboard/mouse profile, no settings dialog. The upstream default profile is
# Cxbx's "Cute1": WASD move, mouse look, Space=A, E=B, Q=X, Click1=Y, C/X
# triggers, Return=Start, Backspace=Back.
cat > "$RUN/ghostpc.ini" <<'INI'
[video]
Resolution=1280x960
DisplayMode=windowed
VSync=1

[input]
InputDevice=keyboardmouse
MouseSensitivity=100

[multiplayer]
MatchMinutes=10

[launcher]
ShowSettings=0
INI

TS=$(date +%Y%m%d-%H%M%S)
LOG="$ROOT/logs/ghostpc-ubuntu-$TS.log"

export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT"
export STEAM_COMPAT_DATA_PATH="$SCGHOST_PREFIX"
export PROTON_USE_NTSYNC=1
# GE-Proton starts xalia.exe (gamepad UI accessibility) at 0x00400000. GhostPC
# maps Ghost.exe at its preferred 0x00400000, and a relocated image breaks its
# absolute pointers, so keep that address free.
export PROTON_USE_XALIA=0
export PROTON_NO_XIM=1
export WINE_ALLOW_XIM=0
export XMODIFIERS="@im=none"
export GTK_IM_MODULE=""
export QT_IM_MODULE=""
export XIM=""
export XIM_PROGRAM=""
# A local d3d9.dll (release DXVK) overrides Proton's bundled build. GE-Proton11-1
# ships a DXVK master snapshot that loses the Intel Arc device; release 2.2..2.7.1
# do not. Drop the x32/d3d9.dll from a dxvk-<ver>.tar.gz into run/ to use it.
if [ -f "$RUN/d3d9.dll" ]; then
    export WINEDLLOVERRIDES="d3d9=n,b${WINEDLLOVERRIDES:+;$WINEDLLOVERRIDES}"
    echo "DXVK override: $RUN/d3d9.dll"
fi
export GHOSTPC_UBUNTU_TRACE="${GHOSTPC_UBUNTU_TRACE:-1}"
export GHOSTPC_UBUNTU_LOG="C:\\ghostpc-ubuntu-build.log"
if [ "${RENDERER:-dxvk}" = "wine" ]; then
    export PROTON_USE_WINED3D=1
    echo "Renderer: wined3d (OpenGL)"
else
    echo "Renderer: DXVK (Vulkan)"
fi

cd "$RUN"
echo "Launching $RUN/GhostPC.exe"
echo "Logs: $LOG"
echo "      $RUN/ghostpc.log"
setsid "$GE_PROTON_DIR/proton" run ./GhostPC.exe > "$LOG" 2>&1 &
echo "started (pid $!)"
