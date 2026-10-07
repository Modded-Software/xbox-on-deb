#!/usr/bin/env python3
"""Relay a physical Xbox controller into a virtual Xbox pad that Wine sees.

Why: Wine/Proton only exposes gamepads to XInput when they are recognised
Xbox-style HID devices.  The physical "Microsoft Xbox Series S|X Controller"
here is enumerated by the kernel but never reaches Wine's XInput slots, so
games (and Cxbx, which binds port 0 to "XInput/0/Gamepad") get no input.

This reads the physical pad's evdev events and re-emits them through a uinput
device shaped like an Xbox One pad (VID:PID 045e:02d1), which Wine already
recognises as an XInput-compatible device.  Result: slot 0 carries the
physical controller.

Usage:
    .venv-recomp/bin/python scripts/gamepad_proxy.py
    .venv-recomp/bin/python scripts/gamepad_proxy.py --list   # show caps only
"""
import argparse
import ctypes
import fcntl
import glob
import os
import select
import struct
import sys

import uinput

BYID = "/dev/input/by-id/usb-Microsoft_Controller_*-event-joystick"
EVIOCGRAB = 0x40044590
ABSINFO = struct.Struct("iiiiii")  # input_absinfo
INPUT_EVENT = struct.Struct("llHHi")

# Standard xpad/xone button set.
BUTTONS = (
    uinput.BTN_SOUTH, uinput.BTN_EAST, uinput.BTN_NORTH, uinput.BTN_WEST,
    uinput.BTN_TL, uinput.BTN_TR, uinput.BTN_SELECT, uinput.BTN_START,
    uinput.BTN_MODE, uinput.BTN_THUMBL, uinput.BTN_THUMBR,
)
AXES = (
    uinput.ABS_X, uinput.ABS_Y, uinput.ABS_Z, uinput.ABS_RX,
    uinput.ABS_RY, uinput.ABS_RZ, uinput.ABS_HAT0X, uinput.ABS_HAT0Y,
)


def find_source():
    matches = glob.glob(BYID)
    if matches:
        return sorted(matches)[0]
    for name in ("/dev/input/js1", "/dev/input/js0"):
        if os.path.exists(name):
            return name
    raise SystemExit("no physical Xbox controller found")


def absinfo(fd, code):
    ioc = 0x80000000 | (ABSINFO.size << 16) | (ord("E") << 8) | (0x40 + code)
    buf = bytearray(ABSINFO.size)
    fcntl.ioctl(fd, ioc, buf)
    _value, minimum, maximum, fuzz, flat, _res = ABSINFO.unpack(buf)
    return minimum, maximum, fuzz, flat


def axis_specs(fd):
    specs = []
    for ev in AXES:
        minimum, maximum, fuzz, flat = absinfo(fd, ev[1])
        specs.append(ev + (minimum, maximum, fuzz, flat))
    return specs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="print capabilities and exit")
    ap.add_argument("--test", action="store_true", help="self-drive the axes (no physical pad)")
    args = ap.parse_args()

    if args.test:
        specs = [ev + (-32768, 32767, 16, 128) for ev in AXES[:6]]
        specs += [uinput.ABS_HAT0X + (-1, 1, 0, 0), uinput.ABS_HAT0Y + (-1, 1, 0, 0)]
        src, fd = "self-test", None
    else:
        src = find_source()
        fd = os.open(src, os.O_RDONLY | os.O_NONBLOCK)
        specs = axis_specs(fd)
    if args.list:
        print(f"source: {src}")
        for ev in specs:
            print(f"  {ev}")
        return

    events = list(BUTTONS) + specs
    device = uinput.Device(
        events, name="Microsoft X-Box One pad",
        bustype=0x03, vendor=0x045E, product=0x02D1, version=0x0000,
    )
    known = {(e[0], e[1]) for e in events}
    print(f"relaying {src} -> virtual Xbox pad (Ctrl+C to stop)", flush=True)

    if args.test:
        import time
        try:
            step = 0
            while True:
                device.emit(uinput.ABS_X, -32768 if step % 2 else 32767, syn=False)
                device.emit(uinput.BTN_SOUTH, step % 3 == 0, syn=False)
                device.syn()
                step += 1
                print(f"tick {step}", flush=True)
                time.sleep(0.3)
        finally:
            device.destroy()
        return

    try:
        fcntl.ioctl(fd, EVIOCGRAB, 1)
    except OSError as exc:
        print(f"warning: could not grab source ({exc}); duplicate possible", file=sys.stderr)

    try:
        while True:
            ready, _, _ = select.select([fd], [], [])
            if not ready:
                continue
            try:
                chunk = os.read(fd, INPUT_EVENT.size * 64)
            except BlockingIOError:
                continue
            for off in range(0, len(chunk) - INPUT_EVENT.size + 1, INPUT_EVENT.size):
                _s, _us, etype, code, value = INPUT_EVENT.unpack_from(chunk, off)
                if etype == 0:          # EV_SYN
                    device.syn()
                elif (etype, code) in known:
                    device.emit((etype, code), value, syn=False)
    finally:
        device.destroy()
        os.close(fd)


if __name__ == "__main__":
    main()