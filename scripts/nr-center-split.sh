#!/bin/bash
# nr-center-split.sh - horizontal 50/50 comparison of two clips:
#   crop the CENTER 50% (half the width, full height) of A and of B, hstack them
#   (A left, B right) into one full-width frame, and take the AUDIO from B only.
#   Both clips are trimmed so they START at START seconds and run to the end.
#
#   bash scripts/nr-center-split.sh A.mp4 B.mp4 OUT.mp4 [START=60] [FPS=60] [B_SHIFT=0]
#
# B_SHIFT (seconds, may be negative) advances B's start relative to A - use it when B's content
# sits behind A's (a positive value seeks B that much further in, i.e. moves B earlier).
#
# Env: VAAPI_DEVICE0 (default /dev/dri/renderD128), NR_QP (default 18).
set -euo pipefail
A=${1:?usage: nr-center-split.sh A.mp4 B.mp4 OUT.mp4 [START] [FPS] [B_SHIFT]}; B=${2:?missing B}; OUT=${3:?missing OUT}
START=${4:-60}; FPS=${5:-60}; BSHIFT=${6:-0}
FF=$HOME/.local/bin/ffmpeg
FP=$HOME/.local/bin/ffprobe
QP=${NR_QP:-18}
B_SS=$( echo "$START + ($BSHIFT)" | bc -l )
"$FF" -nostdin -v error -y -ss "$START" -i "$A" -ss "$B_SS" -i "$B" -filter_complex \
  "[0:v]crop=iw/2:ih:iw/4:0[a];[1:v]crop=iw/2:ih:iw/4:0[b];\
[a][b]hstack=inputs=2,fps=$FPS,format=nv12,hwupload[o]" \
  -map "[o]" -map 1:a:0 -vaapi_device "${VAAPI_DEVICE0:-/dev/dri/renderD128}" -c:v h264_vaapi -qp "$QP" \
  -c:a copy -shortest "$OUT"
echo "nr-center-split: $OUT  (center 50% each, A|B, from ${START}s (+B ${BSHIFT}s), ${FPS} fps, audio from B)"
"$FP" -hide_banner "$OUT" > "$OUT.probe.txt" 2>&1
grep -E "Duration|Stream" "$OUT.probe.txt"