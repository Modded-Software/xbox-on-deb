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

def find_qemu_window():
    """Return the X id of the QEMU display window (client area)."""
    root = x11.XDefaultRootWindow(dpy)
    found = []

    def walk(win, depth):
        if depth > 3:
            return
        name = ctypes.c_char_p()
        if x11.XFetchName(dpy, win, ctypes.byref(name)) and name.value:
            if b"QEMU" in name.value:
                found.append(win)
        child = ctypes.POINTER(ctypes.c_ulong)()
        n = ctypes.c_uint()
        if x11.XQueryTree(dpy, win, ctypes.byref(ctypes.c_ulong()),
                          ctypes.byref(ctypes.c_ulong()),
                          ctypes.byref(child), ctypes.byref(n)):
            for i in range(n.value):
                walk(child[i], depth + 1)

    walk(root, 0)
    if not found:
        raise SystemExit("no QEMU window found")
    return found[-1]


def guest_origin():
    win = find_qemu_window()
    rx = ctypes.c_int()
    ry = ctypes.c_int()
    child = ctypes.c_ulong()
    x11.XTranslateCoordinates(dpy, win, x11.XDefaultRootWindow(dpy), 0, 0,
                              ctypes.byref(rx), ctypes.byref(ry),
                              ctypes.byref(child))
    return rx.value, ry.value

arg = sys.argv[1]

if arg.startswith("move:") or arg.startswith("gmove:"):
    _, xs, ys = arg.split(":")
    x, y = int(xs), int(ys)
    if arg.startswith("g"):
        ox, oy = guest_origin()
        x += ox
        y += oy
    xtst.XTestFakeMotionEvent(dpy, -1, x, y, 0)
    x11.XFlush(dpy)
    print(f"moved {xs},{ys}")
    raise SystemExit(0)

if arg.startswith("click:") or arg.startswith("rclick:") or arg.startswith("gclick:"):
    _, xs, ys = arg.split(":")
    x, y = int(xs), int(ys)
    button = 3 if arg.startswith("rclick") else 1
    if arg.startswith("g"):
        ox, oy = guest_origin()
        x += ox
        y += oy
    xtst.XTestFakeMotionEvent(dpy, -1, x, y, 0)
    x11.XFlush(dpy)
    time.sleep(0.2)
    xtst.XTestFakeButtonEvent(dpy, button, 1, 0)
    xtst.XTestFakeButtonEvent(dpy, button, 0, 0)
    x11.XFlush(dpy)
    print(f"clicked {x},{y} button {button}")
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
