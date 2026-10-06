#!/usr/bin/env python3
"""xinject -- inject X11 input events via XTEST, for automated testing.

Built on ctypes against the system libX11/libXtst, so there is nothing to
compile. The recompiled game's input path is X11 -> Wine -> framebuffer window
-> src/input, and this drives the first hop deterministically.

Commands:

  xinject list                        list top-level windows (id, size, name)
  xinject focus <title-substr>        raise + focus a matching window
  xinject key <name> down|up|press    XTest key event (name is an X keysym)
  xinject btn <1-3> down|up|click     XTest mouse button
  xinject move <dx> <dy> [n] [ms]      relative pointer motion, n times (sustained)

Exit status is non-zero on a bad command or a missing window, so a test script
can assert on it. Nothing here is game-specific; it is a general X11 tool.
"""

import ctypes
import sys
import time

CurrentTime = 0
RevertToParent = 2

_x11 = ctypes.CDLL("libX11.so.6")
_xtst = ctypes.CDLL("libXtst.so.6")

c_void_p = ctypes.c_void_p


def _declare():
    _x11.XOpenDisplay.restype = c_void_p
    _x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    _x11.XDefaultRootWindow.restype = ctypes.c_ulong
    _x11.XDefaultRootWindow.argtypes = [c_void_p]
    _x11.XStringToKeysym.restype = ctypes.c_ulong
    _x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
    _x11.XKeysymToKeycode.restype = ctypes.c_ubyte
    _x11.XKeysymToKeycode.argtypes = [c_void_p, ctypes.c_ulong]
    _x11.XQueryTree.restype = ctypes.c_int
    _x11.XQueryTree.argtypes = [c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
                                ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
                                ctypes.POINTER(ctypes.c_uint)]
    _x11.XFetchName.restype = ctypes.c_int
    _x11.XFetchName.argtypes = [c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_char_p)]
    _x11.XGetGeometry.restype = ctypes.c_int
    _x11.XGetGeometry.argtypes = [c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
                                  ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
                                  ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint),
                                  ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint)]
    _x11.XSetInputFocus.restype = ctypes.c_int
    _x11.XSetInputFocus.argtypes = [c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    _x11.XRaiseWindow.restype = ctypes.c_int
    _x11.XRaiseWindow.argtypes = [c_void_p, ctypes.c_ulong]
    _x11.XFlush.restype = ctypes.c_int
    _x11.XFlush.argtypes = [c_void_p]
    _x11.XSync.restype = ctypes.c_int
    _x11.XSync.argtypes = [c_void_p, ctypes.c_int]
    _x11.XCloseDisplay.restype = ctypes.c_int
    _x11.XCloseDisplay.argtypes = [c_void_p]
    _x11.XFree.restype = ctypes.c_int
    _x11.XFree.argtypes = [c_void_p]

    _xtst.XTestFakeKeyEvent.restype = ctypes.c_int
    _xtst.XTestFakeKeyEvent.argtypes = [c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
    _xtst.XTestFakeButtonEvent.restype = ctypes.c_int
    _xtst.XTestFakeButtonEvent.argtypes = [c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
    _xtst.XTestFakeRelativeMotionEvent.restype = ctypes.c_int
    _xtst.XTestFakeRelativeMotionEvent.argtypes = [c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]


_declare()


def window_name(win):
    name = ctypes.c_char_p()
    if _x11.XFetchName(_dpy, win, ctypes.byref(name)) and name.value is not None:
        text = name.value.decode("utf-8", "replace")
        _x11.XFree(name)
        return text
    return ""


def window_size(win):
    root = ctypes.c_ulong()
    x = ctypes.c_int()
    y = ctypes.c_int()
    w = ctypes.c_uint()
    h = ctypes.c_uint()
    bw = ctypes.c_uint()
    depth = ctypes.c_uint()
    if _x11.XGetGeometry(_dpy, win, ctypes.byref(root), ctypes.byref(x), ctypes.byref(y),
                         ctypes.byref(w), ctypes.byref(h), ctypes.byref(bw), ctypes.byref(depth)):
        return (int(w.value), int(h.value))
    return (0, 0)


def children(win):
    root_ret = ctypes.c_ulong()
    parent_ret = ctypes.c_ulong()
    kids = ctypes.POINTER(ctypes.c_ulong)()
    n = ctypes.c_uint()
    if not _x11.XQueryTree(_dpy, win, ctypes.byref(root_ret), ctypes.byref(parent_ret),
                           ctypes.byref(kids), ctypes.byref(n)):
        return []
    result = [kids[i] for i in range(n.value)]
    if kids:
        _x11.XFree(kids)
    return result


def find_window(win, needle, depth=0):
    if needle.lower() in window_name(win).lower():
        w, h = window_size(win)
        if w and h:
            return win
    for child in children(win):
        found = find_window(child, needle, depth + 1)
        if found:
            return found
    return 0


def list_windows(win, depth=0):
    w, h = window_size(win)
    print(f"{'  ' * depth}0x{win:08x} {w}x{h} {window_name(win)}")
    for child in children(win):
        list_windows(child, depth + 1)


def do_key(name, action):
    keysym = _x11.XStringToKeysym(name.encode())
    if not keysym:
        print(f"xinject: unknown keysym '{name}'", file=sys.stderr)
        return 3
    keycode = _x11.XKeysymToKeycode(_dpy, keysym)
    if not keycode:
        print(f"xinject: no keycode for '{name}'", file=sys.stderr)
        return 3
    if action in ("down", "press"):
        _xtst.XTestFakeKeyEvent(_dpy, keycode, 1, CurrentTime)
    if action in ("up", "press"):
        _xtst.XTestFakeKeyEvent(_dpy, keycode, 0, CurrentTime)
    if action not in ("down", "up", "press"):
        print("xinject: key action must be down|up|press", file=sys.stderr)
        return 3
    _x11.XFlush(_dpy)
    print(f"key {name} {action} keycode {keycode}")
    return 0


def do_btn(number, action):
    if action in ("down", "click"):
        _xtst.XTestFakeButtonEvent(_dpy, number, 1, CurrentTime)
    if action in ("up", "click"):
        _xtst.XTestFakeButtonEvent(_dpy, number, 0, CurrentTime)
    _x11.XFlush(_dpy)
    print(f"btn {number} {action}")
    return 0


def main(argv):
    global _dpy
    if len(argv) < 2:
        print(__doc__.strip().splitlines()[0], file=sys.stderr)
        return 2
    _dpy = _x11.XOpenDisplay(None)
    if not _dpy:
        print("xinject: cannot open X display", file=sys.stderr)
        return 2

    cmd = argv[1]
    if cmd == "list":
        list_windows(_x11.XDefaultRootWindow(_dpy))
    elif cmd == "focus" and len(argv) >= 3:
        win = find_window(_x11.XDefaultRootWindow(_dpy), argv[2])
        if not win:
            print(f"xinject: no window matching '{argv[2]}'", file=sys.stderr)
            _x11.XCloseDisplay(_dpy)
            return 4
        _x11.XRaiseWindow(_dpy, win)
        _x11.XSetInputFocus(_dpy, win, RevertToParent, CurrentTime)
        _x11.XFlush(_dpy)
        w, h = window_size(win)
        print(f"focused 0x{win:08x} {w}x{h}")
    elif cmd == "title" and len(argv) >= 3:
        win = find_window(_x11.XDefaultRootWindow(_dpy), argv[2])
        if not win:
            print(f"xinject: no window matching '{argv[2]}'", file=sys.stderr)
            return 4
        print(window_name(win))
    elif cmd == "wait" and len(argv) >= 3:
        secs = float(argv[3]) if len(argv) >= 4 else 60.0
        deadline = time.time() + secs
        win = 0
        while time.time() < deadline:
            win = find_window(_x11.XDefaultRootWindow(_dpy), argv[2])
            if win:
                break
            time.sleep(0.5)
        if not win:
            print(f"xinject: timed out waiting for '{argv[2]}'", file=sys.stderr)
            return 4
        print(f"0x{win:08x} {window_name(win)}")
    elif cmd == "key" and len(argv) >= 4:
        return do_key(argv[2], argv[3])
    elif cmd == "btn" and len(argv) >= 4:
        return do_btn(int(argv[2]), argv[3])
    elif cmd == "move" and len(argv) >= 4:
        dx, dy = int(argv[2]), int(argv[3])
        count = int(argv[4]) if len(argv) >= 5 else 1
        interval = (float(argv[5]) / 1000.0) if len(argv) >= 6 else 0.0
        for i in range(count):
            _xtst.XTestFakeRelativeMotionEvent(_dpy, dx, dy, CurrentTime)
            _x11.XFlush(_dpy)
            if interval and i + 1 < count:
                time.sleep(interval)
        print(f"move {dx} {dy} x{count}")
    else:
        print("xinject: bad command", file=sys.stderr)
        return 2

    _x11.XSync(_dpy, 0)
    _x11.XCloseDisplay(_dpy)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
