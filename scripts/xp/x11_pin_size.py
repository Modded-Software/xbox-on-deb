#!/usr/bin/env python3
"""Pin an X11 window to its current size so the WM cannot resize it.

    x11_pin_size.py "QEMU (Windows XP-0)" [--wait SECONDS]

Sets WM_NORMAL_HINTS min == max == current size. Used by scripts/30-xp-vm.sh so
the VM window stays exactly one guest pixel per screen pixel.
"""
import ctypes
import sys
import time

x11 = ctypes.CDLL("libX11.so.6")
x11.XOpenDisplay.restype = ctypes.c_void_p
x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
x11.XDefaultRootWindow.restype = ctypes.c_ulong
x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
x11.XQueryTree.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                           ctypes.POINTER(ctypes.c_ulong),
                           ctypes.POINTER(ctypes.c_ulong),
                           ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
                           ctypes.POINTER(ctypes.c_uint)]
x11.XFetchName.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                           ctypes.POINTER(ctypes.c_char_p)]
x11.XGetWindowAttributes.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                                     ctypes.c_void_p]
x11.XSetWMNormalHints.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p]
x11.XResizeWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_uint, ctypes.c_uint]
x11.XFlush.argtypes = [ctypes.c_void_p]
x11.XFree.argtypes = [ctypes.c_void_p]


class XSizeHints(ctypes.Structure):
    _fields_ = [
        ("flags", ctypes.c_long),
        ("x", ctypes.c_int), ("y", ctypes.c_int),
        ("width", ctypes.c_int), ("height", ctypes.c_int),
        ("min_width", ctypes.c_int), ("min_height", ctypes.c_int),
        ("max_width", ctypes.c_int), ("max_height", ctypes.c_int),
        ("width_inc", ctypes.c_int), ("height_inc", ctypes.c_int),
        ("min_aspect_x", ctypes.c_int), ("min_aspect_y", ctypes.c_int),
        ("max_aspect_x", ctypes.c_int), ("max_aspect_y", ctypes.c_int),
        ("base_width", ctypes.c_int), ("base_height", ctypes.c_int),
        ("win_gravity", ctypes.c_int),
    ]


class XWindowAttributes(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_int), ("y", ctypes.c_int),
        ("width", ctypes.c_int), ("height", ctypes.c_int),
        ("border_width", ctypes.c_int), ("depth", ctypes.c_int),
        ("visual", ctypes.c_void_p), ("root", ctypes.c_ulong),
        ("class_", ctypes.c_int), ("bit_gravity", ctypes.c_int),
        ("win_gravity", ctypes.c_int), ("backing_store", ctypes.c_int),
        ("backing_planes", ctypes.c_ulong), ("backing_pixel", ctypes.c_ulong),
        ("save_under", ctypes.c_int), ("colormap", ctypes.c_ulong),
        ("map_installed", ctypes.c_int), ("map_state", ctypes.c_int),
        ("all_event_masks", ctypes.c_long), ("your_event_mask", ctypes.c_long),
        ("do_not_propagate_mask", ctypes.c_long), ("override_redirect", ctypes.c_int),
        ("screen", ctypes.c_void_p),
    ]


# Windows come and go while --keep loops; a destroyed window would otherwise
# abort the process through the default Xlib error handler.
_ERRHANDLER = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
x11.XSetErrorHandler.argtypes = [_ERRHANDLER]
x11.XSetErrorHandler.restype = ctypes.c_void_p


def _ignore_x_errors(_dpy, _err):
    return 0


_ERRHANDLER_INSTANCE = _ERRHANDLER(_ignore_x_errors)
x11.XSetErrorHandler(_ERRHANDLER_INSTANCE)

PSize, PMinSize, PMaxSize = 8, 16, 32


def find(dpy, root, title, out):
    r, p = ctypes.c_ulong(), ctypes.c_ulong()
    kids = ctypes.POINTER(ctypes.c_ulong)()
    n = ctypes.c_uint()
    if not x11.XQueryTree(dpy, root, ctypes.byref(r), ctypes.byref(p),
                          ctypes.byref(kids), ctypes.byref(n)):
        return
    for i in range(n.value):
        w = kids[i]
        name = ctypes.c_char_p()
        if x11.XFetchName(dpy, w, ctypes.byref(name)) and name.value:
            if name.value.decode("utf-8", "replace").startswith(title):
                out.append(w)
            x11.XFree(name)
        find(dpy, w, title, out)
    if kids:
        x11.XFree(kids)


def main():
    title = sys.argv[1]
    wait = 15.0
    if "--wait" in sys.argv:
        wait = float(sys.argv[sys.argv.index("--wait") + 1])
    keep = 0.0
    if "--keep" in sys.argv:
        keep = float(sys.argv[sys.argv.index("--keep") + 1])
    forced = None
    if "--size" in sys.argv:
        w_s, h_s = sys.argv[sys.argv.index("--size") + 1].lower().split("x")
        forced = (int(w_s), int(h_s))
    dpy = x11.XOpenDisplay(None)
    if not dpy:
        raise SystemExit("cannot open display")
    root = x11.XDefaultRootWindow(dpy)
    deadline = time.time() + wait
    found = []
    while time.time() < deadline:
        found = []
        find(dpy, root, title, found)
        if found:
            break
        time.sleep(0.5)
    if not found:
        raise SystemExit(f"no window titled {title!r}")

    deadline = time.time() + keep if keep else 0
    while True:
      found = []
      find(dpy, root, title, found)
      # QEMU creates small hidden helper windows with the same title prefix. Pin
      # each match to its own current size: the display window is already 1:1
      # (zoom-to-fit off), and the frame/parent windows get pinned too.
      pinned = []
      for w in found:
        attrs = XWindowAttributes()
        x11.XGetWindowAttributes(dpy, w, ctypes.byref(attrs))
        hints = XSizeHints()
        hints.flags = PSize | PMinSize | PMaxSize
        if forced:
            hints.width = hints.min_width = hints.max_width = forced[0]
            hints.height = hints.min_height = hints.max_height = forced[1]
        else:
            hints.width = hints.min_width = hints.max_width = attrs.width
            hints.height = hints.min_height = hints.max_height = attrs.height
        x11.XSetWMNormalHints(dpy, w, ctypes.byref(hints))
        if forced and (attrs.width, attrs.height) != forced:
            # Force the size now as well: QEMU sizes the window to the guest
            # video mode, which would otherwise shrink it during the boot.
            x11.XResizeWindow(dpy, w, forced[0], forced[1])
        pinned.append(f"{attrs.width}x{attrs.height}")
    x11.XFlush(dpy)
    print(f"pinned {title}: {', '.join(pinned)}")


if __name__ == "__main__":
    main()
