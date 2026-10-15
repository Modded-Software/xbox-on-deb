#!/bin/bash
# Post-process a captured game video and file it in the user's Videos dir:
# drop the tail, fade the picture to black, then move it to ~/Videos.
#
#   bash scripts/24-process-video.sh [input] [options]
#
#   input        a video path; the newest logs/video-*.mp4 when omitted
#   --tail N     seconds to remove from the end      (default 10)
#   --fade N     fade-to-black length in seconds     (default 2)
#   --dest DIR   destination directory               (default ~/Videos)
#   --keep       leave the source file where it is
#   --sw-dec     decode on the CPU instead of the GPU
#   --foreground run in the foreground instead of detaching
#
# DETACHED by default (setsid): prints the pid, output path, live progress file
# and log, then returns. Kill with `kill $(cat <pidfile>)`.
#
# GPU path (default): decode, fade and encode all on the A770 media engine.
#   -init_hw_device vaapi=va:DEV -filter_hw_device va  (the FFmpeg 8 way to
#   bind hwupload to a device) + hwdownload,format=nv12,fade,format=nv12,hwupload
#   then h264_vaapi (low-power/VDEnc). --sw-dec drops -hwaccel (CPU decode) but
#   keeps GPU scale/encode. VAAPI_DEVICE=/dev/dri/renderD129 picks GPU1.
#
# Video and audio are processed in SEPARATE passes and copy-muxed, because a
# single pass that carries video+audio interleaving here wedges after ~3.5s
# (ffmpeg 8 / i915). See recomp/diary/ for the investigation.
set -u
ROOT="${REPO_ROOT:-$HOME/WORKSPACE-VM/projects/xbox-on-deb}"
cd "$ROOT" || exit 1
export PATH="$HOME/.local/bin:$PATH"

VAAPI_DEVICE="${VAAPI_DEVICE:-/dev/dri/renderD128}"
TAIL="${TAIL:-10}"
FADE="${FADE:-2}"
QP="${QP:-20}"
DEST_DIR="${DEST_DIR:-$HOME/Videos}"
KEEP="${KEEP:-0}"
HW_DECODE="${HW_DECODE:-1}"
FOREGROUND="${FOREGROUND:-0}"
INPUT="${INPUT:-}"

while [ $# -gt 0 ]; do
    case "$1" in
        --tail) TAIL="$2"; shift 2 ;;
        --fade) FADE="$2"; shift 2 ;;
        --dest) DEST_DIR="$2"; shift 2 ;;
        --keep) KEEP=1; shift ;;
        --sw-dec) HW_DECODE=0; shift ;;
        --foreground) FOREGROUND=1; shift ;;
        -h|--help) echo "usage: $0 [input] [--tail N] [--fade N] [--dest DIR] [--keep] [--sw-dec] [--foreground]"; exit 0 ;;
        -*) echo "unknown option: $1" >&2; exit 2 ;;
        *) INPUT="$1"; shift ;;
    esac
done

if [ -z "$INPUT" ]; then
    INPUT=$(ls -t logs/video-*.mp4 | grep -m1 .)
fi
if [ -z "$INPUT" ] || [ ! -f "$INPUT" ]; then
    echo "no input video (pass a path or have a logs/video-*.mp4)" >&2
    exit 1
fi

[ -n "$(command -v ffmpeg)" ]  || { echo "ffmpeg not found (put the BtbN build in ~/.local/bin)" >&2; exit 1; }
[ -n "$(command -v ffprobe)" ] || { echo "ffprobe not found" >&2; exit 1; }

mkdir -p "$DEST_DIR" logs
base=$(basename "$INPUT")
final="$DEST_DIR/$base"
tmp="$DEST_DIR/.$base.tmp.mp4"
vid="$DEST_DIR/.$base.vid.mp4"
aud="$DEST_DIR/.$base.aud.m4a"
prog="$ROOT/logs/process-video-$base.progress"
logf="$ROOT/logs/process-video-$base.log"
pidf="$ROOT/logs/process-video-$base.pid"

dur=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$INPUT")
if [ -z "$dur" ]; then
    echo "could not read duration of $INPUT" >&2
    exit 1
fi
has_audio=$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$INPUT" | grep -m1 .)

int_part="${dur%%.*}"
frac_part="${dur#*.}"
[ "$frac_part" = "$dur" ] && frac_part=0
frac3="${frac_part:0:3}"
while [ "${#frac3}" -lt 3 ]; do frac3="${frac3}0"; done
dur_ms=$(( 10#$int_part * 1000 + 10#$frac3 ))
end_ms=$(( dur_ms - TAIL * 1000 )); [ "$end_ms" -lt 0 ] && end_ms=0
fade_st_ms=$(( end_ms - FADE * 1000 )); [ "$fade_st_ms" -lt 0 ] && fade_st_ms=0
printf -v end_s     '%d.%03d' $(( end_ms / 1000 ))     $(( end_ms % 1000 ))
printf -v fade_st_s '%d.%03d' $(( fade_st_ms / 1000 )) $(( fade_st_ms % 1000 ))

DEC=(-init_hw_device "vaapi=va:$VAAPI_DEVICE" -filter_hw_device va)
if [ "$HW_DECODE" != "0" ]; then
    DEC+=(-hwaccel vaapi -hwaccel_device "$VAAPI_DEVICE" -hwaccel_output_format vaapi)
    VF="hwdownload,format=nv12,fade=t=out:st=$fade_st_s:d=$FADE,format=nv12,hwupload"
else
    VF="fade=t=out:st=$fade_st_s:d=$FADE,format=nv12,hwupload"
fi

echo "input    : $INPUT (${dur}s, audio=${has_audio:-none})"
echo "output   : $final"
echo "keep     : ${end_s}s  (remove last ${TAIL}s, fade ${FADE}s from ${fade_st_s}s)"
echo "vaapi    : $VAAPI_DEVICE   hw_decode=$HW_DECODE"
echo "progress : $prog"
echo "log      : $logf"

if [ "$FOREGROUND" != "1" ]; then
    rm -f "$prog"
    setsid env INPUT="$INPUT" TAIL="$TAIL" FADE="$FADE" DEST_DIR="$DEST_DIR" \
        KEEP="$KEEP" HW_DECODE="$HW_DECODE" VAAPI_DEVICE="$VAAPI_DEVICE" FOREGROUND=1 \
        bash "$ROOT/scripts/24-process-video.sh" >> "$logf" 2>&1 &
    echo $! > "$pidf"
    echo "launched pid $(cat "$pidf")  (kill: kill \$(cat $pidf))"
    exit 0
fi

rm -f "$prog" "$vid" "$aud" "$tmp" "$DEST_DIR/.$base.aud.wav"
echo "== pass 1/4: video (fade, GPU) ==" >> "$logf"
ffmpeg -hide_banner -y -nostdin "${DEC[@]}" -i "$INPUT" \
    -t "$end_s" -map 0:v:0 -an \
    -vf "$VF" \
    -c:v h264_vaapi -low_power 1 -qp "$QP" \
    -progress "$prog" -nostats -loglevel info \
    "$vid" >> "$logf" 2>&1
status=$?
if [ "$status" != "0" ]; then
    echo "video pass failed (exit $status); see $logf" >&2
    rm -f "$pidf"; exit "$status"
fi

if [ -n "$has_audio" ]; then
    wav="$DEST_DIR/.$base.aud.wav"
    rm -f "$wav"
    # The AAC decoder and the AAC encoder deadlock when they sit in one ffmpeg
    # process (any filter in between, even aresample, does not help). Routing
    # the faded audio through a PCM intermediate in a separate process works.
    echo "== pass 2/4: audio decode + fade -> pcm ==" >> "$logf"
    ffmpeg -hide_banner -y -nostdin -i "$INPUT" -t "$end_s" -vn -map 0:a:0 \
        -af "afade=t=out:st=$fade_st_s:d=$FADE" -c:a pcm_s16le \
        -loglevel info "$wav" >> "$logf" 2>&1
    astatus=$?
    echo "== pass 3/4: pcm -> aac ==" >> "$logf"
    ffmpeg -hide_banner -y -nostdin -i "$wav" -c:a aac -b:a 192k \
        -loglevel info "$aud" >> "$logf" 2>&1
    astatus2=$?
    echo "== pass 4/4: mux (copy) ==" >> "$logf"
    ffmpeg -hide_banner -y -nostdin -i "$vid" -i "$aud" \
        -map 0:v:0 -map 1:a:0 -c copy -movflags +faststart \
        -loglevel info "$tmp" >> "$logf" 2>&1
    status=$?
    if [ "$status" != "0" ]; then
        echo "mux failed (exit $status, audio pass $astatus/$astatus2); see $logf" >&2
        rm -f "$pidf"; exit "$status"
    fi
    rm -f "$vid" "$aud" "$wav"
else
    mv -f "$vid" "$tmp"
fi

mv -f "$tmp" "$final"
if [ "$KEEP" = "0" ] && [ "$(readlink -f "$INPUT")" != "$(readlink -f "$final")" ]; then
    rm -f "$INPUT"
fi
echo "done: $final"
# Report the finished file's duration/size to the console and the log. Run the
# probe once and branch on its status explicitly: piping into `tee` would report
# tee's exit status and hide a probe failure.
if probe=$(ffprobe -v error -show_entries format=duration,size \
        -of default=noprint_wrappers=1 "$final" 2>&1); then
    printf '%s\n' "$probe"
else
    echo "ffprobe failed for $final" >&2
fi
printf '%s\n' "$probe" >> "$logf"
rm -f "$pidf"
exit 0