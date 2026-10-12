#!/bin/bash
# NR-convert a video: ffmpeg decode -> nr_frame --stream (raw BGRA, one live runtime with
# temporal history) -> ffmpeg encode (VAAPI h264 on the A770), source audio kept. No PNGs.
#   bash scripts/nr-video.sh IN.mp4 OUT.mp4 [RENDER_SCALE=0.5] [extra ffmpeg input args, e.g. -t 10]
# Per-frame timing: OUT.mp4.log
set -euo pipefail
IN=$1; OUT=$2; RS=${3:-0.5}; shift $(( $# < 3 ? $# : 3 ))
R=$(cd "$(dirname "${BASH_SOURCE[0]}")/../refs/dlss-on-arc" 2>&1 && pwd) || R=$PWD/refs/dlss-on-arc
export PATH=$HOME/.local/bin:/usr/bin:/bin:$PATH
IFS=, read -r W H FPS < <(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate \
                          -of csv=p=0 "$IN")
ffmpeg -v error -nostdin "$@" -i "$IN" -f rawvideo -pix_fmt bgra - \
| (cd "$R" && ./work/nr_frame --stream "${W}x${H}" --render-scale "$RS" 2> "$OUT.log") \
| ffmpeg -v error -y -f rawvideo -pix_fmt bgra -s "${W}x${H}" -r "$FPS" -i - "$@" -i "$IN" \
    -map 0:v -map 1:a? -vaapi_device "${VAAPI_DEVICE:-/dev/dri/renderD128}" \
    -vf 'format=nv12,hwupload' -c:v h264_vaapi -qp 18 -c:a aac -shortest "$OUT"
tail -n 1 "$OUT.log"
