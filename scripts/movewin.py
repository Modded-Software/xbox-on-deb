#!/usr/bin/env python3
"""Move an X11 top-level window matching a title substring to a position.

Needed because xdotool/wmctrl are not installed. Used to relocate Wine's
virtual-desktop window onto the ultrawide monitor without touching GNOME's
monitor configuration.

Usage: movewin.py "TITLE-SUBSTRING" X Y
"""
import ctypes
import sys
import time

x11 = ctypes.CDLL("libX11.so.6")
x11.XOpenDisplay.restype = ctypes.c_void_p
x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
x11.XDefaultRootWindow.restype = ctypes.c_ulong
x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
x11.XQueryTree.argtypes = [
    ctypes.c_void_p, ctypes.c_ulong,
    ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
    ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)), ctypes.POINTER(ctypes.c_uint),
]
x11.XFetchName.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_char_p)]
x11.XMoveWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int]
x11.XFlush.argtypes = [ctypes.c_void_p]
x11.XFree.argtypes = [ctypes.c_void_p]


def children(dpy, win):
    root = ctypes.c_ulong()
    parent = ctypes.c_ulong()
    arr = ctypes.POINTER(ctypes.c_ulong)()
    n = ctypes.c_uint()
    ok = x11.XQueryTree(dpy, win, ctypes.byref(root), ctypes.byref(parent),
                        ctypes.byref(arr), ctypes.byref(n))
    if ok == 0:
        return []
    out = [arr[i] for i in range(n.value)]
    if arr:
        x11.XFree(arr)
    return out


def name(dpy, win):
    nm = ctypes.c_char_p()
    if x11.XFetchName(dpy, win, ctypes.byref(nm)) == 0 or not nm.value:
        return ""
    out = nm.value.decode("utf-8", "replace")
    x11.XFree(nm)
    return out


def walk(dpy, win, want, depth, hits):
    if depth > 4:
        return
    for w in children(dpy, win):
        n = name(dpy, w)
        if want.lower() in n.lower():
            hits.append(w)
        walk(dpy, w, want, depth + 1, hits)


def main():
    want, xs, ys = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    dpy = x11.XOpenDisplay(None)
    if not dpy:
        raise SystemExit("cannot open display")
    root = x11.XDefaultRootWindow(dpy)
    for _ in range(20):
        hits = []
        walk(dpy, root, want, 0, hits)
        if hits:
            for w in hits:
                x11.XMoveWindow(dpy, w, xs, ys)
            x11.XFlush(dpy)
            print(f"moved {len(hits)} window(s) matching '{want}' to {xs},{ys}")
            return
        time.sleep(1)
    print(f"no window matching '{want}' found")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
