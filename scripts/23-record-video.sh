#!/bin/bash
# Record the game window (video) and ghost.exe's own audio to an MP4.
#
#   bash scripts/23-record-video.sh start [NAME]   # waits for the window, records in the background
#   bash scripts/23-record-video.sh stop           # finalise -> logs/video-<NAME>.mp4
#
# Video: ffmpeg x11grab of the Wine window (Xwayland, found by title), encoded
# on an A770 media engine (h264_vaapi, low-power/VDEnc) -- no CPU encode; the
# BGRX->NV12 conversion also runs on the GPU (scale_vaapi), which cut ffmpeg
# from ~44% to ~10-17% of one core (the rest is x11grab's frame copy). The
# encode runs on GPU0 (renderD128) by default so GPU1, which the game owns,
# is untouched; VAAPI_DEVICE=/dev/dri/renderD129 picks GPU1. Needs an ffmpeg
# with VAAPI (BtbN linux64 GPL build in ~/.local/bin).
# Audio: pw-record of the ghost.exe PipeWire stream (the static ffmpeg has no
# pulse input). The two are muxed on stop; if the game window closes first,
# ffmpeg ends on its own and `stop` still muxes what was captured. ffmpeg
# lives in ~/.local/bin (static build, no sudo).
set -u
ROOT=/home/agent/WORKSPACE-VM/projects/xbox-on-deb
cd "$ROOT"
export PATH="$HOME/.local/bin:$PATH"
STATE=/tmp/opencode/record-video
mkdir -p "$STATE" logs
TITLE="${TITLE:-StarCraft: Ghost}"
FPS="${FPS:-60}"
VAAPI_DEVICE="${VAAPI_DEVICE:-/dev/dri/renderD128}"

find_window() {
    xwininfo -root -tree | grep -m1 "\"$TITLE" | grep -o "0x[0-9a-f]*" | grep -m1 .
}

case "${1:-}" in
start)
    NAME="${2:-$(date +%Y%m%d-%H%M%S)}"
    win=""
    for _ in $(seq 1 120); do
        win=$(find_window)
        [ -n "$win" ] && break
        sleep 1
    done
    if [ -z "$win" ]; then echo "no window titled '$TITLE'" >&2; exit 1; fi
    echo "$NAME" > "$STATE/name"
    ffmpeg -hide_banner -loglevel warning -y -vaapi_device "$VAAPI_DEVICE" \
        -f x11grab -framerate "$FPS" -window_id "$win" -i "${DISPLAY:-:0}" \
        -vf "crop=trunc(iw/2)*2:trunc(ih/2)*2,hwupload,scale_vaapi=format=nv12" \
        -c:v h264_vaapi -low_power 1 -qp 20 \
        "$STATE/video.mkv" > "$STATE/ffmpeg.log" 2>&1 &
    echo $! > "$STATE/ffmpeg.pid"
    pw-record --target ghost.exe --rate 48000 --channels 2 --format s16 \
        "$STATE/audio.wav" > "$STATE/pw.log" 2>&1 &
    echo $! > "$STATE/pw.pid"
    echo "recording window $win as '$NAME' (stop: bash scripts/23-record-video.sh stop)"
    ;;
stop)
    [ -f "$STATE/name" ] || { echo "not recording" >&2; exit 1; }
    NAME=$(cat "$STATE/name")
    for p in ffmpeg pw; do
        [ -f "$STATE/$p.pid" ] && kill -INT "$(cat "$STATE/$p.pid")"
    done
    sleep 2
    OUT="logs/video-$NAME.mp4"
    if [ -s "$STATE/audio.wav" ]; then
        ffmpeg -hide_banner -loglevel warning -y -i "$STATE/video.mkv" -i "$STATE/audio.wav" \
            -c:v copy -c:a aac -b:a 192k -shortest "$OUT"
    else
        echo "no ghost.exe audio captured; video only" >&2
        ffmpeg -hide_banner -loglevel warning -y -i "$STATE/video.mkv" -c copy "$OUT"
    fi
    rm -f "$STATE"/name "$STATE"/*.pid
    echo "wrote $OUT"
    ;;
*)
    echo "usage: $0 start [NAME] | stop" >&2
    exit 2
    ;;
esac
