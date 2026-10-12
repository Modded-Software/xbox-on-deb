#!/usr/bin/env python3
"""Send a key to an X11 window via XTest (no xdotool needed).

Usage: sendkey.py KEY [WINDOW_ID]
  KEY       e.g. F2, F5, F9, Return, space
  WINDOW_ID optional hex id to focus first (e.g. 0x3200030)
"""
import ctypes
import sys
import time

XK = {
    "F2": 0xFFBF, "F5": 0xFFC2, "F9": 0xFFC6, "F10": 0xFFC7, "F3": 0xFFC0,
    "Return": 0xFF0D, "space": 0x0020, "Escape": 0xFF1B, "Tab": 0xFF09,
    "UP": 0xFF52, "DOWN": 0xFF54, "LEFT": 0xFF51, "RIGHT": 0xFF53,
}

x11 = ctypes.CDLL("libX11.so.6")
xtst = ctypes.CDLL("libXtst.so.6")
x11.XOpenDisplay.restype = ctypes.c_void_p
x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
x11.XKeysymToKeycode.restype = ctypes.c_uint
x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
x11.XSetInputFocus.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
x11.XFlush.argtypes = [ctypes.c_void_p]
xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
xtst.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
xtst.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]

dpy = x11.XOpenDisplay(None)
if not dpy:
    raise SystemExit("cannot open display")

arg = sys.argv[1]

if arg.startswith("click:"):
    _, xs, ys = arg.split(":")
    x, y = int(xs), int(ys)
    xtst.XTestFakeMotionEvent(dpy, -1, x, y, 0)
    x11.XFlush(dpy)
    time.sleep(0.2)
    xtst.XTestFakeButtonEvent(dpy, 1, 1, 0)
    xtst.XTestFakeButtonEvent(dpy, 1, 0, 0)
    x11.XFlush(dpy)
    print(f"clicked {x},{y}")
    raise SystemExit(0)

if len(sys.argv) > 2:
    win = int(sys.argv[2], 16)
    x11.XSetInputFocus(dpy, win, 1, 0)  # RevertToParent, CurrentTime
    time.sleep(0.2)

keysym = XK.get(arg, ord(arg[0]) if len(arg) == 1 else None)
if keysym is None:
    raise SystemExit(f"unknown key {arg}")

kc = x11.XKeysymToKeycode(dpy, keysym)
xtst.XTestFakeKeyEvent(dpy, kc, 1, 0)
xtst.XTestFakeKeyEvent(dpy, kc, 0, 0)
x11.XFlush(dpy)
print(f"sent {arg} (keycode {kc})")
