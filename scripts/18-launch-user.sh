#!/bin/bash
# Launch the recompiled game for hands-on testing.
#
# The default environment matches what recomp/tests/framework.py launches with
# (which reaches the menu and a mission reliably): keyboard+mouse, input
# diagnostics, and each run's own timestamped log. The repeating watchdog is
# NOT enabled by default -- it suspends the guest thread every interval to
# sample its RIP, which can wedge a load -- and neither is the vblank
# override. Both are opt-in via WATCH=1 / VBLANK=1 for diagnosis.
#
# setsid puts the game in its own session, so it survives the command that
# started it.
set -u
ROOT="${REPO_ROOT:-$HOME/WORKSPACE-VM/projects/xbox-on-deb}"
cd "$ROOT"
source "$ROOT/scripts/config.sh" || exit 1   # GPU pin (DRI_PRIME) etc. loaded here too
mkdir -p logs

# stop any stale instance (wineserver -k covers the whole prefix)
bash scripts/16-stop-recomp.sh

TS=$(date +%Y%m%d-%H%M%S)
RUNLOG="$ROOT/logs/runtime-$TS.log"
ln -sf "runtime-$TS.log" "$ROOT/logs/latest-runtime.log"

EXTRA=""
if [ "${WATCH:-0}" != "0" ]; then
    EXTRA="$EXTRA RECOMP_WATCHDOG_SECS=15 RECOMP_WATCHDOG_REPEAT=1"
fi
if [ "${VBLANK:-0}" != "0" ]; then
    EXTRA="$EXTRA RECOMP_VBLANK=1"
fi
# Flip-stall sampler (diagnosis only): dumps the guest thread stack while frames
# are frozen, without exiting. RECOMP_STALL_DUMP=1 make replay-session SESSION=<id>
if [ "${RECOMP_STALL_DUMP:-0}" != "0" ]; then
    EXTRA="$EXTRA RECOMP_STALL_DUMP=1"
fi
# Pushbuffer kick statistics (diagnosis only): kicks/s, walk ms, ack CPU%.
if [ "${RECOMP_KICK_STATS:-0}" != "0" ]; then
    EXTRA="$EXTRA RECOMP_KICK_STATS=1"
fi
# APU/XAudio2 diagnostics and raw PCM capture (diagnosis only).
if [ -n "${RECOMP_APU_WAV:-}" ]; then
    EXTRA="$EXTRA RECOMP_APU_WAV=$RECOMP_APU_WAV"
fi
if [ "${RECOMP_APU_DIAG:-0}" != "0" ]; then
    EXTRA="$EXTRA RECOMP_APU_DIAG=1"
fi
# Graphics optimisation A/B knobs (see docs/20-optimisation-plan-1080p.md).
if [ -n "${RECOMP_ASYNC_FLIP:-}" ]; then
    EXTRA="$EXTRA RECOMP_ASYNC_FLIP=$RECOMP_ASYNC_FLIP"
fi
if [ -n "${RECOMP_PRESENT_SNAPSHOT:-}" ]; then
    EXTRA="$EXTRA RECOMP_PRESENT_SNAPSHOT=$RECOMP_PRESENT_SNAPSHOT"
fi
if [ "${RECOMP_HASHDBG:-0}" != "0" ]; then
    EXTRA="$EXTRA RECOMP_HASHDBG=1"
fi
if [ "${RECOMP_CLOAKDBG:-0}" != "0" ]; then
    EXTRA="$EXTRA RECOMP_CLOAKDBG=1"
fi
for knob in RECOMP_NV2A_NATIVE_FENCES RECOMP_SYNC_LAG RECOMP_LAZY_FLIP \
            RECOMP_DEPTH_PUBLISH RECOMP_TEX_VALIDATE_ONCE RECOMP_SW_METHOD_DROP \
            RECOMP_EVENT_ADOPT RECOMP_SWIZZLED_SURFACE_VIEW; do
    value=$(printenv "$knob")
    if [ -n "$value" ]; then
        EXTRA="$EXTRA $knob=$value"
    fi
done
if [ "${RECOMP_NV2A_GPU_TIMING:-0}" != "0" ]; then
    EXTRA="$EXTRA RECOMP_NV2A_GPU_TIMING=1"
fi

# Input recording/replay, keyed by an explicit SESSION id so recordings never
# collide and replay names exactly the session to reproduce. The game reads and
# writes inside the prefix (C:\ maps to pfx/drive_c); the host path is printed.
#   make record-session SESSION=ghost-crash
#   make replay-session SESSION=ghost-crash
SESSION="${SESSION:-}"
REC_WIN=""
if [ -n "$SESSION" ]; then
    REC_WIN="C:\\recomp-record-${SESSION}.txt"
    RECORD_PATH="$SCGHOST_PREFIX/pfx/drive_c/recomp-record-${SESSION}.txt"
fi
if [ "${REPLAY:-0}" != "0" ]; then
    if [ -z "$SESSION" ]; then
        echo "REPLAY=1 requires SESSION=<id> (which recording to replay)" >&2
        exit 2
    fi
    EXTRA="$EXTRA RECOMP_INPUT_REPLAY=$REC_WIN"
    RECORD=0
elif [ "${RECORD:-1}" != "0" ] && [ -n "$SESSION" ]; then
    EXTRA="$EXTRA RECOMP_INPUT_RECORD=$REC_WIN"
else
    RECORD=0
fi

# RESOLUTION=WxH is forwarded to the launcher as --resolution=WxH.
# Default to 1080p; override with RESOLUTION=1280x720 (or empty for native).
export RESOLUTION="${RESOLUTION-1920x1080}"

env KBM=1 DIAG=1 RECOMP_KEY_TRACE=1 RECOMP_LOG="$RUNLOG" $EXTRA \
    setsid bash scripts/14-launch-recomp.sh > logs/launch.out 2>&1 &

echo "launched; window title is 'StarCraft: Ghost'"
echo "  runtime log : logs/runtime-$TS.log  (logs/latest-runtime.log)"
echo "  launcher log: logs/launch.out"
echo "  watchdog    : ${WATCH:-0}   vblank: ${VBLANK:-0}"
if [ "${REPLAY:-0}" != "0" ]; then
    echo "  input replay: session '$SESSION'  -> $RECORD_PATH"
elif [ "${RECORD:-1}" != "0" ]; then
    echo "  input record: session '$SESSION'  -> $RECORD_PATH"
    echo "  replay it   : make replay-session SESSION=$SESSION"
else
    echo "  input record: off (set SESSION=<id> to record, or RECORD=0 to silence)"
fi
echo "  stop with   : make stop"
