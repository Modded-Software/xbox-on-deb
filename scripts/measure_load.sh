#!/bin/bash
# Measure Cxbx load milestones for one settings configuration.
#
# Kills any running session, clears .reslog markers, launches, and records the
# wall-clock time at which the game creates each resource-log marker:
#   startup.reslog  -> emulation started
#   menu.reslog     -> main menu reached
#   *Miners_Bunker* -> first level loading
#
# Usage: measure_load.sh <label> [timeout-seconds]
LABEL="${1:?usage: measure_load.sh <label> [timeout]}"
TMO="${2:-480}"

cd /home/agent/WORKSPACE-VM/projects/xbox-on-deb
source "$PWD/scripts/config.env"
detect_ge_proton
GAMEDIR="extracted/StarCraft Ghost Xbox Finn Hillbilly"

WINEPREFIX="$SCGHOST_PREFIX/pfx" "$GE_PROTON_DIR/files/bin/wineserver" -k
sleep 5

rm -f "$GAMEDIR"/*.reslog

T0=$(date +%s)
setsid bash scripts/03-launch-xbox-build.sh "$GAMEDIR/Ghost.xbe" \
    > "logs/load_${LABEL}.log" 2>&1 &

START=""
MENU=""
LEVEL=""
DEADLINE=$((T0 + TMO))
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    sleep 5
    NOW=$(date +%s)
    if [ -z "$START" ] && [ -f "$GAMEDIR/startup.reslog" ]; then
        START=$((NOW - T0))
    fi
    if [ -z "$MENU" ] && [ -f "$GAMEDIR/menu.reslog" ]; then
        MENU=$((NOW - T0))
    fi
    if [ -z "$LEVEL" ]; then
        for f in "$GAMEDIR"/*Miners_Bunker*.reslog; do
            if [ -f "$f" ]; then
                LEVEL=$((NOW - T0))
            fi
        done
    fi
    if [ -n "$LEVEL" ]; then
        break
    fi
done

{
    echo "label=$LABEL"
    echo "startup_seconds=$START"
    echo "menu_seconds=$MENU"
    echo "level_seconds=$LEVEL"
} > "logs/load_${LABEL}.times"

echo "RESULT label=$LABEL startup=$START menu=$MENU level=$LEVEL"
