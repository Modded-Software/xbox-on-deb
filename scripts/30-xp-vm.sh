#!/bin/bash
# Windows XP SP3 in QEMU/KVM - a period-correct desktop for recording demo videos.
#
#   bash scripts/30-xp-vm.sh install [ISO]   # boot the XP CD and install
#   bash scripts/30-xp-vm.sh run             # boot the installed system
#   bash scripts/30-xp-vm.sh stop            # power off a running VM
#   bash scripts/30-xp-vm.sh status          # is it running, where is the disk
#   bash scripts/30-xp-vm.sh iso [ISO]       # show/point at the install media
#
# The ISO is never in the repo (licensing): put xp.iso in the VM dir or pass a
# path. Disk images live in ~/Games/xp-vm and are qcow2 (sparse).
#
# Record it like the game: the window is titled "Windows XP", so
#   TITLE="Windows XP" AUDIO_TARGET=qemu-system-i386 bash scripts/23-record-video.sh start xp
# or simply:  make record-video TITLE="Windows XP"   (see the Makefile targets)
#
# Hardware is chosen for XP's in-box drivers only - no virtio, no extra disks:
#   IDE disk/CD, rtl8139 NIC (user-mode NAT), AC97 audio, USB tablet, Cirrus VGA.
# Cirrus caps at 1024x768; VGA=std with a VBEMP/VESA driver gets further.
set -euo pipefail

# Keep the QEMU window on XWayland: x11grab (scripts/23) and XTest clicks only
# see X11 windows, and a native Wayland window is invisible to both.
export GDK_BACKEND="${XP_GDK_BACKEND:-x11}"

VM_DIR="${XP_VM_DIR:-$HOME/Games/xp-vm}"
ROOT="${REPO_ROOT:-$PWD}"
PIN_TITLE="${XP_WINDOW_TITLE:-QEMU (Windows XP}"
XFER_ISO="${XP_XFER_ISO:-$VM_DIR/transfer.iso}"
DISK="$VM_DIR/xp.qcow2"
DISK_SIZE="${XP_DISK_SIZE:-8G}"
PID="$VM_DIR/qemu.pid"
QEMU="${QEMU:-/usr/bin/qemu-system-i386}"
RAM="${XP_RAM:-1024}"
SMP="${XP_SMP:-2}"
CPU="${XP_CPU:-host}"
DISPLAY_KIND="${XP_DISPLAY:-gtk,zoom-to-fit=on,show-menubar=off}"
VGA="${XP_VGA:-cirrus}"
NET="${XP_NET:-rtl8139}"
TITLE="${XP_TITLE:-Windows XP}"
MON="$VM_DIR/monitor.sock"

find_iso() {
    if [ -n "${1:-}" ]; then echo "$1"; return; fi
    if [ -n "${XP_ISO:-}" ]; then echo "$XP_ISO"; return; fi
    if [ -f "$VM_DIR/xp.iso" ]; then echo "$VM_DIR/xp.iso"; return; fi
    echo ""
}

running() {
    [ -f "$PID" ] || return 1
    kill -0 "$(cat "$PID")" 2>&1 || return 1
}

qemu_args() {
    QARGS=(
        -name "Windows XP"
        -machine pc -accel kvm -cpu "$CPU" -smp "$SMP" -m "$RAM"
        -rtc base=localtime
        -display "$DISPLAY_KIND" -vga "$VGA"
        -usb -device usb-tablet
        -audiodev "$AUDIODEV" -device "AC97,audiodev=snd0"
        -nic "user,model=$NET"
        -monitor "unix:$MON,server,nowait"
        -drive "file=$DISK,if=ide,format=qcow2,cache=writeback"
    )
    # Optional second CD (E:) for moving files into the guest, see `xfer`.
    if [ -f "$XFER_ISO" ]; then
        QARGS+=(-drive "file=$XFER_ISO,media=cdrom,if=ide,index=3,readonly=on")
    fi
}

mon() {
    printf '%s\n' "$@" | nc -U -N -w 2 "$MON"
}

# Type literal text into the guest through the HMP sendkey names.
type_keys() {
    local s="$1" i ch k lc
    for ((i = 0; i < ${#s}; i++)); do
        ch="${s:i:1}"
        case "$ch" in
            [a-z]) k="$ch" ;;
            [A-Z]) lc="${ch,,}"; k="shift-$lc" ;;
            [0-9]) k="$ch" ;;
            ' ') k="spc" ;;
            ':') k="shift-semicolon" ;;
            '\\') k="backslash" ;;
            '.') k="dot" ;;
            '-') k="minus" ;;
            '/') k="slash" ;;
            '_') k="shift-minus" ;;
            '"') k="shift-apostrophe" ;;
            *) continue ;;
        esac
        mon "sendkey $k" > /tmp/opencode/xp-mon-reply.txt 2>&1
        sleep 0.05
    done
}

# 1:1 window: pin the outer size to the guest pixels and forbid the WM resize.
pin_window() {
    local force="${2:-}"
    if [ -n "$force" ]; then
        uv run python "$ROOT/scripts/xp/x11_pin_size.py" "$PIN_TITLE" --wait "${1:-15}" --size "$force"
    else
        uv run python "$ROOT/scripts/xp/x11_pin_size.py" "$PIN_TITLE" --wait "${1:-15}"
    fi
}

# Guest audio to a WAV file instead of the host sound card: the demo recorder
# muxes it in, so nothing from the host (mic, other apps) leaks into the video.
if [ -n "${XP_AUDIO_WAV:-}" ]; then
    AUDIODEV="wav,id=snd0,path=$XP_AUDIO_WAV"
elif [ -n "${XP_AUDIO_SINK:-}" ]; then
    # Route the guest to a named PipeWire sink (the demo recorder captures
    # that sink's monitor, so nothing from the host leaks into the video).
    AUDIODEV="pipewire,id=snd0,out.name=$XP_AUDIO_SINK"
else
    AUDIODEV="${XP_AUDIODEV:-pa},id=snd0"
fi

case "${1:-}" in
install)
    ISO=$(find_iso "${2:-}")
    if [ -z "$ISO" ] || [ ! -f "$ISO" ]; then
        echo "no XP ISO. Pass one, or drop it at $VM_DIR/xp.iso" >&2
        exit 1
    fi
    if running; then echo "VM already running (pid $(cat "$PID"))" >&2; exit 1; fi
    mkdir -p "$VM_DIR"
    [ -f "$DISK" ] || qemu-img create -f qcow2 "$DISK" "$DISK_SIZE"
    echo "installing from $ISO"
    echo "  disk: $DISK ($DISK_SIZE)"
    FLOPPY=()
    if [ -f "$VM_DIR/unattend.img" ]; then
        FLOPPY=(-drive "file=$VM_DIR/unattend.img,format=raw,if=floppy")
        echo "  unattended: $VM_DIR/unattend.img"
    fi
    qemu_args
    "$QEMU" "${QARGS[@]}" -boot d -cdrom "$ISO" "${FLOPPY[@]}" > "$VM_DIR/qemu.log" 2>&1 &
    echo $! > "$PID"
    echo "installer running (pid $!), window 'Windows XP'"
    echo "progress: bash scripts/30-xp-vm.sh snap   stop: bash scripts/30-xp-vm.sh stop"
    ;;

run)
    if running; then echo "VM already running (pid $(cat "$PID"))" >&2; exit 1; fi
    if [ ! -f "$DISK" ]; then echo "$DISK not found; run: $0 install <iso>" >&2; exit 1; fi
    mkdir -p "$VM_DIR"
    qemu_args
    "$QEMU" "${QARGS[@]}" -boot c > "$VM_DIR/qemu.log" 2>&1 &
    echo $! > "$PID"
    echo "Windows XP running (pid $!), disk $DISK"
    # One fixed window for the whole session: QEMU asks for a new size on every
    # guest video-mode change, so the hints are re-applied for as long as the
    # VM lives (zoom-to-fit scales the guest into that fixed window).
    if [ "${XP_PIN:-1}" = 1 ]; then
        uv run python "$ROOT/scripts/xp/x11_pin_size.py" "$PIN_TITLE" --wait 20 \
            --size "${XP_PIN_SIZE:-1280x1024}" --keep 86400 \
            > "$VM_DIR/pin.log" 2>&1 &
        echo $! > "$VM_DIR/pin.pid"
        echo "window: fixed ${XP_PIN_SIZE:-1280x1024} (XP_PIN=0 to disable)"
    fi
    echo "stop:  bash scripts/30-xp-vm.sh stop"
    ;;

pin)
    # pin [WAIT] [WxH]: pin to the current size, or force WxH.
    pin_window "${2:-15}" "${3:-}"
    ;;

stop)
    if [ -f "$VM_DIR/pin.pid" ]; then
        kill "$(cat "$VM_DIR/pin.pid")" >> "$VM_DIR/pin.log" 2>&1
        rm -f "$VM_DIR/pin.pid"
    fi
    if ! running; then echo "not running"; rm -f "$PID"; exit 0; fi
    P=$(cat "$PID")
    kill -TERM "$P"
    for _ in $(seq 1 30); do
        kill -0 "$P" 2>&1 || break
        sleep 0.5
    done
    if kill -0 "$P" 2>&1; then
        echo "still alive after SIGTERM, sending SIGKILL to $P" >&2
        kill -KILL "$P"
    fi
    rm -f "$PID"
    echo "stopped"
    ;;

status)
    if running; then echo "running: pid $(cat "$PID")"; else echo "not running"; fi
    echo "vm dir: $VM_DIR"
    [ -d "$VM_DIR" ] && ls -la "$VM_DIR"
    ;;

iso)
    if [ -n "${2:-}" ]; then
        mkdir -p "$VM_DIR"
        ln -sfn "$(readlink -f "$2")" "$VM_DIR/xp.iso"
        echo "$VM_DIR/xp.iso -> $(readlink -f "$2")"
    else
        f=$(find_iso)
        if [ -n "$f" ]; then echo "$f"; else echo "no ISO configured"; fi
    fi
    ;;

snap)
    # Screen dump through the QEMU monitor, converted to PNG for a progress check.
    OUT="${2:-/tmp/opencode/xp-screen.png}"
    PPM="${OUT%.png}.ppm"
    running || { echo "not running" >&2; exit 1; }
    mon "screendump $PPM" > /tmp/opencode/xp-mon-reply.txt 2>&1
    sleep 1
    "$HOME/.local/bin/ffmpeg" -nostdin -v error -y -i "$PPM" "$OUT"
    echo "$OUT"
    ;;

keys)
    # keys <name>...: raw HMP key names (ret, tab, shift-d, ...).
    running || { echo "not running" >&2; exit 1; }
    shift
    for k in "$@"; do mon "sendkey $k" > /tmp/opencode/xp-mon-reply.txt 2>&1; sleep 0.15; done
    ;;

type)
    # type <text>: type a literal string into the guest.
    running || { echo "not running" >&2; exit 1; }
    type_keys "${2:-}"
    ;;

mon)
    running || { echo "not running" >&2; exit 1; }
    shift
    mon "$@"
    ;;

eject)
    # Eject the second CD (the data disc on E:).
    running || { echo "not running" >&2; exit 1; }
    mon "eject ${XP_CD_DEV:-ide1-cd1}" > /tmp/opencode/xp-mon-reply.txt 2>&1
    echo "ejected ${XP_CD_DEV:-ide1-cd1}"
    ;;

insert)
    # insert <iso>: put a disc in the second CD drive (label shown by Windows).
    running || { echo "not running" >&2; exit 1; }
    iso=$(readlink -f "${2:-}")
    [ -f "$iso" ] || { echo "no such ISO: ${2:-}" >&2; exit 1; }
    mon "change ${XP_CD_DEV:-ide1-cd1} $iso" > /tmp/opencode/xp-mon-reply.txt 2>&1
    echo "inserted $iso"
    ;;

*)
    echo "usage: $0 install [iso] | run | stop | status | pin | iso [path] | snap [png] | keys <k>... | type <text> | mon <cmd> | eject | insert <iso>" >&2
    exit 2
    ;;
esac
