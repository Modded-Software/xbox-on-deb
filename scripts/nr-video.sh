#!/bin/bash
# nr-video.sh - NR-convert a video with NO intermediate frames on disk and NO software decode:
#     VAAPI(GPU) h264 decode -> raw BGRA over a pipe -> nr_frame --stream (one live runtime,
#     temporal history) -> VAAPI(GPU) h264 encode.  Video only (no audio).
# Splits the clip across BOTH A770s by default (one nr_frame process + one VAAPI device each),
# then concatenates; set NR_JOBS=1 to use a single device (writes straight to OUT).
#
#   bash scripts/nr-video.sh IN.mp4 OUT.mp4 [RENDER_SCALE=0.5] [extra ffmpeg input args...]
#
# Env: NR_JOBS (default 2), NR_GPU_BACKEND (default vulkan), VAAPI_DEVICE0/1, NR_QP (default 18).
# Per-frame timing lines land in OUT.log. Any extra args (e.g. "-ss 30 -t 2") force NR_JOBS=1.
set -euo pipefail
IN=${1:?usage: nr-video.sh IN OUT [RENDER_SCALE] [ffmpeg args]}; OUT=${2:?missing OUT}
RS=${3:-0.5}; shift $(( $# < 3 ? $# : 3 ))
EXTRA=("$@")
JOBS=${NR_JOBS:-2}; [ ${#EXTRA[@]} -gt 0 ] && JOBS=1          # extra args => single clip, no split
R=$PWD/refs/dlss-on-arc
D=$(dirname "${BASH_SOURCE[0]}")
if [ -d "$D/../refs/dlss-on-arc" ]; then R=$(cd "$D/../refs/dlss-on-arc" && pwd); fi
FF=$HOME/.local/bin/ffmpeg
FP=$HOME/.local/bin/ffprobe
export PATH=$HOME/.local/bin:$PATH
export NR_GPU_BACKEND=${NR_GPU_BACKEND:-vulkan}
QP=${NR_QP:-18}
IFS=, read -r W H FPS < <( "$FP" -v error -select_streams v:0 \
        -show_entries stream=width,height,r_frame_rate -of csv=p=0 "$IN" )
DUR=$( "$FP" -v error -show_entries format=duration -of csv=p=0 "$IN" )
TMPD=$(dirname "$OUT")

dev(){ if [ "$1" = 0 ]; then echo "${VAAPI_DEVICE0:-/dev/dri/renderD128}"; else echo "${VAAPI_DEVICE1:-/dev/dri/renderD129}"; fi; }

seg(){ # JOB DEV SS T OUTSEG  (SS/T may be empty)
  local j=$1 d=$2 ss=$3 t=$4 out=$5 seek=()
  [ -n "$ss" ] && seek=(-ss "$ss")
  [ -n "$t" ]  && seek+=(-t "$t")
  "$FF" -nostdin -v error -hwaccel vaapi -hwaccel_device "$d" -hwaccel_output_format vaapi \
        ${EXTRA[@]+"${EXTRA[@]}"} "${seek[@]}" -i "$IN" \
        -vf 'hwdownload,format=bgra' -f rawvideo -pix_fmt bgra - \
  | ( cd "$R" && XMX_DEVICE=$j ./work/nr_frame --stream "${W}x${H}" --render-scale "$RS" 2> "$out.log" ) \
  | "$FF" -nostdin -v error -y -f rawvideo -pix_fmt bgra -s "${W}x${H}" -r "$FPS" -i - \
        -vaapi_device "$d" -vf 'format=nv12,hwupload' -c:v h264_vaapi -qp "$QP" "$out"
}

if [ "$JOBS" -le 1 ]; then
  seg 0 "$(dev 0)" "" "" "$OUT"
else
  HALF=$( echo "scale=6; $DUR/2" | bc )
  SEG0=$TMPD/.nr-seg0.mp4; SEG1=$TMPD/.nr-seg1.mp4
  seg 0 "$(dev 0)" ""      "$HALF" "$SEG0" &
  P0=$!
  seg 1 "$(dev 1)" "$HALF" ""      "$SEG1" &
  P1=$!
  wait "$P0"; wait "$P1"
  printf "file '%s'\nfile '%s'\n" "$SEG0" "$SEG1" > "$TMPD/.nr-list.txt"
  "$FF" -nostdin -v error -y -f concat -safe 0 -i "$TMPD/.nr-list.txt" -c copy "$OUT"
  cat "$SEG0.log" "$SEG1.log" > "$OUT.log"
  rm -f "$SEG0" "$SEG1" "$SEG0.log" "$SEG1.log" "$TMPD/.nr-list.txt"
fi
echo "nr-video: $OUT  (${W}x${H} @ ${FPS}, render-scale $RS, ${JOBS} job(s), qp $QP)"