#!/bin/bash
# nr-stitch-fade.sh - concatenate two clips (A then B, video+audio) into one file at a common
#   frame rate, and fade the last FADE seconds to black (video) / silence (audio).
#
#   bash scripts/nr-stitch-fade.sh A.mp4 B.mp4 OUT.mp4 [FADE=3] [FPS=60] [AFADE_IN=0] [AFADE_IN_START=0] [TITLE]
#
# Audio: muted for the first AFADE_IN_START seconds, then faded in over AFADE_IN seconds, then the
# last FADE seconds faded out.
# TITLE: if set, a bold white all-caps sans-serif caption is drawn in the TOP-RIGHT corner over the
# second clip (B) only - the A/B comparison part.
#
# Env: VAAPI_DEVICE0 (default /dev/dri/renderD128), NR_QP (default 18).
#
# Two passes: (1) concat A+B at a common fps (VAAPI encode), (2) fade the last FADE seconds of the
# concatenated file (VAAPI encode). A fade start inside the multi-input filter graph drifts against
# the concatenated timeline, so it is applied on the finished file in pass 2.
set -euo pipefail
A=${1:?usage: nr-stitch-fade.sh A.mp4 B.mp4 OUT.mp4 [FADE] [FPS]}; B=${2:?missing B}; OUT=${3:?missing OUT}
FADE=${4:-3}; FPS=${5:-60}; AFADE_IN=${6:-0}; AFADE_IN_START=${7:-0}; TITLE=${8:-}
FONT=${NR_FONT:-/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf}
FF=$HOME/.local/bin/ffmpeg
FP=$HOME/.local/bin/ffprobe
QP=${NR_QP:-18}
DEV=${VAAPI_DEVICE0:-/dev/dri/renderD128}
TMP="$(dirname "$OUT")/.nr-stitch-tmp.mp4"
DT=""
[ -n "$TITLE" ] && DT=",drawtext=fontfile=${FONT}:text='${TITLE}':fontcolor=white:fontsize=56:x=w-tw-48:y=48"

"$FF" -nostdin -v error -y -i "$A" -i "$B" -filter_complex \
  "[0:v]fps=$FPS,setpts=PTS-STARTPTS[v0];[1:v]fps=$FPS,setpts=PTS-STARTPTS${DT}[v1];\
[v0][v1]concat=n=2:v=1:a=0,format=nv12,hwupload[v];\
[0:a]aformat=sample_rates=48000:channel_layouts=stereo,asetpts=PTS-STARTPTS[a0];\
[1:a]aformat=sample_rates=48000:channel_layouts=stereo,asetpts=PTS-STARTPTS[a1];\
[a0][a1]concat=n=2:v=0:a=1[a]" \
  -map "[v]" -map "[a]" -vaapi_device "$DEV" -c:v h264_vaapi -qp "$QP" -c:a aac -b:a 192k "$TMP"

D=$( "$FP" -v error -show_entries format=duration -of csv=p=0 "$TMP" )
ST=$( echo "$D - $FADE" | bc -l )
MUTE=""
[ "$AFADE_IN_START" != "0" ] && MUTE="volume=enable='lt(t,$AFADE_IN_START)':volume=0,"
"$FF" -nostdin -v error -y -i "$TMP" -vf "fade=t=out:st=$ST:d=$FADE,format=nv12,hwupload" \
  -af "${MUTE}afade=t=in:st=$AFADE_IN_START:d=$AFADE_IN,afade=t=out:st=$ST:d=$FADE" \
  -vaapi_device "$DEV" -c:v h264_vaapi -qp "$QP" -c:a aac -b:a 192k "$OUT"
rm -f "$TMP"
echo "nr-stitch-fade: $OUT  (A + B @ ${FPS} fps, total ${D}s, video fade-out ${FADE}s from ${ST}s, audio muted ${AFADE_IN_START}s then fade-in ${AFADE_IN}s / fade-out ${FADE}s)"
"$FP" -hide_banner "$OUT" > "$OUT.probe.txt" 2>&1
grep -E "Duration|Stream" "$OUT.probe.txt"