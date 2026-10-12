#!/usr/bin/env python3
"""Create a virtual Xbox-style gamepad via /dev/uinput and emit a scripted
event sequence, so Wine/DInput can see a controller (StarCraft: Ghost's Win32
menu ignores keyboard).

Usage:
    gamepad.py [step ...]
Steps (in order):
    wait:<ms>                 sleep
    key:<NAME>:<0|1>          press/release a button
    abs:<NAME>:<value>        set an axis
    syn                       SYN_REPORT (auto-added after each key/abs group)

Button names: SOUTH EAST NORTH WEST TL TR START SELECT MODE
Axis names:   X Y RX RY HAT0X HAT0Y
Example (advance the menu):
    gamepad.py wait:20000 key:SOUTH:1 wait:150 key:SOUTH:0
"""
import ctypes
import fcntl
import struct
import sys
import time

UINPUT = "/dev/uinput"

UI_SET_EVBIT = 0x40045564
UI_SET_KEYBIT = 0x40045565
UI_SET_ABSBIT = 0x40045567
UI_DEV_CREATE = 0x5501
UI_DEV_DESTROY = 0x5502

EV_SYN, EV_KEY, EV_ABS = 0x00, 0x01, 0x03
SYN_REPORT = 0x00

BTN = {
    "SOUTH": 0x130, "EAST": 0x131, "NORTH": 0x133, "WEST": 0x134,
    "TL": 0x136, "TR": 0x137, "SELECT": 0x13a, "START": 0x13b, "MODE": 0x13c,
}
ABS = {"X": 0, "Y": 1, "RX": 3, "RY": 4, "HAT0X": 16, "HAT0Y": 17}

ABS_MAX = 255
HAT_MAX = 1

INPUT_EVENT = struct.Struct("llHHi")


def emit(fd, etype, code, value):
    ev = INPUT_EVENT.pack(0, 0, etype, code, value)
    written = ctypes.CDLL(None).write(fd, ev, len(ev))
    assert written == len(ev), f"short write ({written})"
    syn = INPUT_EVENT.pack(0, 0, EV_SYN, SYN_REPORT, 0)
    ctypes.CDLL(None).write(fd, syn, len(syn))


def create_device():
    fd = ctypes.CDLL(None).open(UINPUT.encode(), 0x0001 | 0x0800 | 0x0400)
    if fd < 0:
        raise SystemExit("could not open /dev/uinput")
    libc = ctypes.CDLL(None)

    def ioctl(number, arg=0):
        if libc.ioctl(fd, number, arg) < 0:
            raise SystemExit(f"ioctl {number:#x}({arg:#x}) failed")

    ioctl(UI_SET_EVBIT, EV_KEY)
    ioctl(UI_SET_EVBIT, EV_ABS)
    for code in BTN.values():
        ioctl(UI_SET_KEYBIT, code)
    for code in ABS.values():
        ioctl(UI_SET_ABSBIT, code)

    # struct uinput_user_dev (legacy): name[80], id(4*u16), ff_effects_max(u32),
    # absmax[64], absmin[64], absfuzz[64], absflat[64]
    name = b"Microsoft X-Box One pad\x00"
    name = name.ljust(80, b"\x00")
    id_ = struct.pack("HHHH", 0x03, 0x045E, 0x02D1, 0x0000)  # BUS_USB, MS, Xbox One
    rest = struct.pack("<I", 0)
    absmax = [0] * 64
    absmin = [0] * 64
    for code in ABS.values():
        absmax[code] = HAT_MAX if code >= 16 else ABS_MAX
    for code in ABS.values():
        if code < 16:
            absmin[code] = -ABS_MAX if code in (1, 3, 4) else 0
    blob = name + id_ + rest + struct.pack("<64i", *absmax) + struct.pack("<64i", *absmin)
    blob += struct.pack("<64i", *([0] * 64)) + struct.pack("<64i", *([0] * 64))
    if libc.write(fd, blob, len(blob)) != len(blob):
        raise SystemExit("failed to write uinput_user_dev")
    ioctl(UI_DEV_CREATE)
    return fd


def main(steps):
    fd = create_device()
    print("virtual gamepad created", flush=True)
    for step in steps:
        parts = step.split(":")
        if parts[0] == "wait":
            time.sleep(int(parts[1]) / 1000.0)
        elif parts[0] == "key":
            emit(fd, EV_KEY, BTN[parts[1]], int(parts[2]))
            print(f"key {parts[1]} {parts[2]}", flush=True)
        elif parts[0] == "abs":
            emit(fd, EV_ABS, ABS[parts[1]], int(parts[2]))
            print(f"abs {parts[1]} {parts[2]}", flush=True)
    print("sequence done; holding device", flush=True)
    try:
        time.sleep(600)
    finally:
        ctypes.CDLL(None).ioctl(fd, UI_DEV_DESTROY)


if __name__ == "__main__":
    main(sys.argv[1:])
