#!/usr/bin/env python3
"""Print the X id of the first window whose title contains a substring.

Usage: x11_window_id.py "QEMU (Windows XP"
Exit status 1 when no window matches. Avoids shell pipelines in scripts.
"""
import ctypes
import sys

x11 = ctypes.CDLL("libX11.so.6")
x11.XOpenDisplay.restype = ctypes.c_void_p
x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
x11.XDefaultRootWindow.restype = ctypes.c_ulong
x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
x11.XQueryTree.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                           ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
                           ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
                           ctypes.POINTER(ctypes.c_uint)]
x11.XFetchName.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_char_p)]


class XWindowAttributes(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int), ("y", ctypes.c_int),
                ("width", ctypes.c_int), ("height", ctypes.c_int),
                ("border_width", ctypes.c_int), ("depth", ctypes.c_int),
                ("visual", ctypes.c_void_p), ("root", ctypes.c_ulong),
                ("class_", ctypes.c_int), ("bit_gravity", ctypes.c_int),
                ("win_gravity", ctypes.c_int), ("backing_store", ctypes.c_int),
                ("backing_planes", ctypes.c_ulong),
                ("backing_pixel", ctypes.c_ulong),
                ("save_under", ctypes.c_int), ("colormap", ctypes.c_ulong),
                ("map_installed", ctypes.c_int), ("map_state", ctypes.c_int),
                ("all_event_masks", ctypes.c_long),
                ("your_event_mask", ctypes.c_long),
                ("do_not_propagate_mask", ctypes.c_long),
                ("override_redirect", ctypes.c_int), ("screen", ctypes.c_void_p)]


x11.XGetWindowAttributes.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                                     ctypes.POINTER(XWindowAttributes)]

args = [a for a in sys.argv[1:] if not a.startswith("--")]
need_ready = "--viewable" in sys.argv[1:]
want_size = "--size" in sys.argv[1:]
needle = args[0] if args else "QEMU"
dpy = x11.XOpenDisplay(None)
if not dpy:
    raise SystemExit("cannot open display")

hits = []


def walk(win, depth):
    if depth > 4:
        return
    name = ctypes.c_char_p()
    if x11.XFetchName(dpy, win, ctypes.byref(name)) and name.value:
        if needle.encode() in name.value:
            hits.append(win)
    root = ctypes.c_ulong()
    parent = ctypes.c_ulong()
    kids = ctypes.POINTER(ctypes.c_ulong)()
    n = ctypes.c_uint()
    if x11.XQueryTree(dpy, win, ctypes.byref(root), ctypes.byref(parent),
                      ctypes.byref(kids), ctypes.byref(n)):
        for i in range(n.value):
            walk(kids[i], depth + 1)


walk(x11.XDefaultRootWindow(dpy), 0)
if not hits:
    raise SystemExit(1)
# The WM reparents guests: the frame and the real client both carry the
# title, and the client (the one to capture or click) is the deeper hit.
win = hits[-1]
if need_ready or want_size:
    attr = XWindowAttributes()
    if not x11.XGetWindowAttributes(dpy, win, ctypes.byref(attr)):
        raise SystemExit(1)
    # IsViewable == 2; a window that is still being mapped or sized is not
    # safe to capture yet (x11grab dies with BadMatch).
    if attr.map_state != 2 or attr.width < 320 or attr.height < 240:
        raise SystemExit(1)
    if want_size:
        print(f"{attr.width}x{attr.height}")
        raise SystemExit(0)
print(hex(win))
