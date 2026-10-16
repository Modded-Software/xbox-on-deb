#!/bin/bash
# nr-alt-compare.sh - A/B alternation comparison video, full-frame (no scaling):
#   play A until SWITCH_AT, then alternate A / B every INTERVAL seconds, and draw a bold white
#   all-caps title in the TOP-RIGHT corner while B (the "output") is on screen.
#
#   bash scripts/nr-alt-compare.sh A.mp4 B.mp4 OUT.mp4 [TITLE] [SWITCH_AT=60] [INTERVAL=5]
#
# Defaults: TITLE="RT + DLSS NR", SWITCH_AT=60 s, INTERVAL=5 s.  Env: NR_FONT, VAAPI_DEVICE0, NR_QP.
set -euo pipefail
A=${1:?usage: nr-alt-compare.sh A.mp4 B.mp4 OUT.mp4 [TITLE] [SWITCH_AT] [INTERVAL]}
B=${2:?missing B}; OUT=${3:?missing OUT}
TITLE=${4:-"RT + DLSS NR"}; SW=${5:-60}; IV=${6:-5}
FF=$HOME/.local/bin/ffmpeg
FONT=${NR_FONT:-/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf}
QP=${NR_QP:-20}
CYC=$(( IV * 2 ))
# B (the output) is shown from SW onward, INTERVAL s on / INTERVAL s off (A first).
EXPR="gte(t\,$SW)*gte(mod(t-$SW\,$CYC)\,$IV)"
"$FF" -nostdin -v error -y -i "$A" -i "$B" -filter_complex \
  "[0:v]setpts=PTS-STARTPTS[a];[1:v]setpts=PTS-STARTPTS[b];\
[a][b]overlay=enable='$EXPR'[ov];\
[ov]drawtext=fontfile=${FONT}:text='${TITLE}':fontcolor=white:fontsize=56:x=w-tw-48:y=48:enable='$EXPR'[t];\
[t]format=nv12,hwupload[o]" \
  -map "[o]" -vaapi_device "${VAAPI_DEVICE0:-/dev/dri/renderD128}" -c:v h264_vaapi -qp "$QP" "$OUT"
echo "nr-alt-compare: $OUT  (A up to ${SW}s, then ${IV}s A / ${IV}s B, title '${TITLE}')"
"$FF" -hide_banner -i "$OUT" > "$OUT.probe.txt" 2>&1
grep -E "Duration|Stream" "$OUT.probe.txt"