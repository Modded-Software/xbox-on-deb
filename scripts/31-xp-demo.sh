#!/bin/bash
# Record a hands-off Windows XP demo: boot, swap in the "SC Ghost" CD, run the
# installer, then keep recording while a human takes over.
#
#   bash scripts/31-xp-demo.sh [NAME] [ISO]
#
# What happens, in front of the camera:
#   1. the VM boots (the data CD that was inserted at boot is ejected first),
#   2. an ISO labelled "SC Ghost" is inserted -> Windows pops the removable
#      media balloon in the taskbar,
#   3. Start > Run is typed and E:\StarCraft-Ghost-Setup.exe is launched,
#   4. recording continues until Ctrl-C *or* the installer window closes.
#
# Output: logs/demo-<NAME>.mp4. Capture itself is delegated to
# scripts/23-record-video.sh (the same x11grab + pw-record + mux path the game
# uses), so the audio starts with the video and cannot drift.
#
#   XP_DEMO_MAX_SECS=600     hard stop (default 1800)
#   XP_DEMO_ISO=/path.iso    use an existing disc image instead of building one
#   XP_DEMO_SETTLE=45        seconds to wait for the desktop after the boot
set -uo pipefail
ROOT="${REPO_ROOT:-$HOME/WORKSPACE-VM/projects/xbox-on-deb}"
cd "$ROOT"
export PATH="$HOME/.local/bin:$PATH"
export GDK_BACKEND="${XP_GDK_BACKEND:-x11}"
# One fixed window size for the whole recording (zoom-to-fit scales the guest
# into it), so the capture area never changes when the guest switches video
# mode during boot.
export XP_DISPLAY="${XP_DISPLAY:-gtk,zoom-to-fit=on,show-menubar=off}"

VM_DIR="${XP_VM_DIR:-$HOME/Games/xp-vm}"
VM="$ROOT/scripts/30-xp-vm.sh"
REC="$ROOT/scripts/23-record-video.sh"
STATE=/tmp/opencode/xp-demo
NAME="${1:-xp-demo-$(date +%Y%m%d-%H%M%S)}"
ISO="${2:-${XP_DEMO_ISO:-$VM_DIR/scghost.iso}}"
MAX_SECS="${XP_DEMO_MAX_SECS:-1800}"
SETTLE="${XP_DEMO_SETTLE:-45}"
FPS="${XP_DEMO_FPS:-30}"
TITLE="QEMU (Windows XP"
# Guest audio goes to a dedicated null sink, whose monitor the recorder reads:
# only the VM's sound ends up in the file (no host apps, no microphone).
SINK="${XP_DEMO_SINK:-scghost}"
OUT="logs/demo-$NAME.mp4"
mkdir -p "$STATE" logs

say() { printf '[demo] %s\n' "$*" >&2; }

cleanup_done=0
probe_n=0
pin_pid=""

alive_pid() {
    [ -n "$1" ] && [ -e "/proc/$1" ]
}

ensure_sink() {
    local dump="$STATE/nodes.txt"
    pw-cli ls Node > "$dump" 2>&1
    if grep -q "node.name = \"$SINK\"" "$dump"; then
        return 0
    fi
    say "creating the '$SINK' audio sink"
    pw-cli create-node adapter "{ factory.name=support.null-audio-sink node.name=$SINK media.class=Audio/Sink object.linger=true audio.position=[FL FR] }" \
        >> "$STATE/quiet.log" 2>&1
    sleep 1
}

stop_recording() {
    [ "$cleanup_done" = 1 ] && return
    cleanup_done=1
    if [ -f /tmp/opencode/record-video/name ]; then
        say "stopping the recorder"
        bash "$REC" stop >> "$STATE/quiet.log" 2>&1
    fi
    if [ -f "$VM_DIR/qemu.pid" ] && alive_pid "$(cat "$VM_DIR/qemu.pid")"; then
        bash "$VM" stop >> "$STATE/quiet.log" 2>&1
        sleep 1
    fi
    if [ -s "logs/video-$NAME.mp4" ]; then
        mv -f "logs/video-$NAME.mp4" "$OUT"
        say "wrote $OUT"
    else
        say "no video captured"
    fi
    if [ -n "$pin_pid" ] && alive_pid "$pin_pid"; then
        kill "$pin_pid" >> "$STATE/quiet.log" 2>&1
    fi
    rm -f "$STATE"/*.ppm
}

trap 'say "interrupted"; stop_recording; exit 130' INT TERM

# --- the disc ---------------------------------------------------------------
build_iso() {
    local iso="$1" tree
    if [ -f "$iso" ] && [ "$iso" -nt "$ROOT/dist/StarCraft-Ghost-Setup-x86.exe" ]; then
        say "using existing disc $iso"
        return
    fi
    if [ ! -f "$ROOT/dist/StarCraft-Ghost-Setup-x86.exe" ]; then
        say "building the 32-bit installer first"
        ARCH=x86 bash "$ROOT/scripts/28-build-installer.sh" >&2
    fi
    tree="$STATE/isodir"
    rm -rf "$tree"
    mkdir -p "$tree"
    cp -al "$VM_DIR/staging/." "$tree/" >> "$STATE/quiet.log" 2>&1 || cp -a "$VM_DIR/staging/." "$tree/"
    cp "$ROOT/dist/StarCraft-Ghost-Setup-x86.exe" "$tree/StarCraft-Ghost-Setup.exe"
    printf '@echo off\r\nrem The installer on this disc is the 32-bit build for Windows XP.\r\n' \
        > "$tree/README.TXT"
    say "building disc $iso"
    genisoimage -quiet -J -R -V "SC Ghost" -o "$iso" "$tree"
}

# --- video ------------------------------------------------------------------
window_id() {
    uv run python "$ROOT/scripts/xp/x11_window_id.py" "$TITLE"
}

window_ready() {
    uv run python "$ROOT/scripts/xp/x11_window_id.py" "$TITLE" --viewable
}

window_size() {
    uv run python "$ROOT/scripts/xp/x11_window_id.py" "$TITLE" --size
}

start_recording() {
    local s1 s2 i win
    for i in $(seq 1 40); do
        win=$(window_ready)
        if [ -z "$win" ]; then sleep 1; continue; fi
        s1=$(window_size)
        sleep 1
        s2=$(window_size)
        if [ "$s1" = "$s2" ] && [ "$s1" = "1280x1024" ]; then
            say "recording window $win ($s1)"
            WINDOW_ID="$win" CROP=1280:1024:0:0 TITLE="$TITLE" \
                AUDIO_PULSE_DEVICE="$SINK.monitor" FPS="$FPS" \
                bash "$REC" start "$NAME" >&2
            return 0
        fi
        say "waiting for the pinned window ($s2)"
        sleep 1
    done
    say "window never reached 1280x1024"
    return 1
}

# --- probes -----------------------------------------------------------------
probe() {
    local mode="$1" ppm
    probe_n=$((probe_n + 1))
    ppm="$STATE/probe-$probe_n.ppm"
    bash "$VM" mon "screendump $ppm" >> "$STATE/quiet.log" 2>&1
    sleep 0.4
    uv run python "$ROOT/scripts/xp/xp_demo_probe.py" "$mode" "$ppm"
    rm -f "$ppm"
}

wait_desktop() {
    local limit=$((SETTLE + 90)) i a b
    say "waiting for the XP desktop"
    for ((i = 0; i < limit; i += 3)); do
        a=$(probe ready)
        if [ "$a" = 1 ]; then
            sleep 2
            b=$(probe ready)
            if [ "$b" = 1 ]; then say "desktop is up"; return 0; fi
        fi
        sleep 3
    done
    say "desktop did not come up in ${limit}s"
    return 1
}

# --- run --------------------------------------------------------------------
[ -f "$VM_DIR/xp.qcow2" ] || { say "no XP disk in $VM_DIR"; exit 1; }
if [ -f "$VM_DIR/qemu.pid" ] && alive_pid "$(cat "$VM_DIR/qemu.pid")"; then
    say "a session is already running; stopping it"
    bash "$VM" stop >> "$STATE/quiet.log" 2>&1
    sleep 2
fi
rm -f /tmp/opencode/record-video/name /tmp/opencode/record-video/*.pid

build_iso "$ISO"
[ -f "$ISO" ] || { say "no disc image"; exit 1; }

ensure_sink
export XP_AUDIO_SINK="$SINK"

say "booting the VM"
if ! bash "$VM" run >> "$STATE/quiet.log"; then
    say "failed to start QEMU"
    exit 1
fi

win=""
for _ in $(seq 1 60); do
    win=$(window_id)
    [ -n "$win" ] && break
    sleep 1
done
if [ -z "$win" ]; then
    say "no QEMU window appeared"
    bash "$VM" stop >> "$STATE/quiet.log" 2>&1
    exit 1
fi
# Roll from the first frame: the BIOS/POST and the XP boot screen are part of
# the demo, so the recorder starts before the desktop check.
start_recording

wait_desktop || { say "giving up"; stop_recording; exit 1; }

# Disc swap, on camera: out with the old, in with the SC Ghost disc. Windows
# pops its removable-media balloon in the taskbar on insertion.
say "ejecting the boot disc"
bash "$VM" eject >> "$STATE/quiet.log" 2>&1
sleep 2
say "inserting the SC Ghost disc"
bash "$VM" insert "$ISO" >> "$STATE/quiet.log" 2>&1
sleep 8

# Start > Run is typed on camera. Retry the whole step if the installer does
# not come up: the desktop is still busy with logon work for a few seconds
# after it is first visible, and keystrokes sent then are dropped.
appeared=0
launched=$SECONDS
for attempt in 1 2 3; do
    say "opening Start > Run (attempt $attempt)"
    bash "$VM" keys meta_l-r >> "$STATE/quiet.log" 2>&1
    sleep 3
    bash "$VM" type 'E:\StarCraft-Ghost-Setup.exe' >> "$STATE/quiet.log" 2>&1
    sleep 1
    bash "$VM" keys ret >> "$STATE/quiet.log" 2>&1
    for _ in $(seq 1 20); do
        sleep 2
        if [ "$(probe alive)" = 1 ]; then appeared=1; break; fi
    done
    [ "$appeared" = 1 ] && break
    say "installer did not appear, retrying"
    sleep 3
done
say "installer launched; the rest is yours (Ctrl-C to finish the recording)"
if [ "$appeared" = 1 ]; then
    say "installer window is up"
else
    say "installer window never appeared; recording the desktop"
fi

# Keep recording while the installer lives. Two seconds per probe, four
# consecutive misses before we believe the window is gone.
misses=0
started=$SECONDS
while :; do
    sleep 2
    if [ $((SECONDS - started)) -ge "$MAX_SECS" ]; then
        say "hit XP_DEMO_MAX_SECS=$MAX_SECS"
        break
    fi
    rec_pid=""
    [ -s /tmp/opencode/record-video/ffmpeg.pid ] && rec_pid=$(cat /tmp/opencode/record-video/ffmpeg.pid)
    if ! alive_pid "$rec_pid"; then
        say "recorder exited"
        break
    fi
    if [ "$(probe alive)" = 1 ]; then
        misses=0
    else
        misses=$((misses + 1))
        if [ "$misses" -ge 4 ]; then
            say "installer window closed"
            break
        fi
    fi
done

stop_recording
exit 0
