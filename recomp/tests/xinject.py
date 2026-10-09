#!/usr/bin/env python3
"""xinject -- inject X11 input events via XTEST, for automated testing.

Built on ctypes against the system libX11/libXtst, so there is nothing to
compile. The recompiled game's input path is X11 -> Wine -> framebuffer window
-> src/input, and this drives the first hop deterministically.

Commands:

  xinject list                        list top-level windows (id, size, name)
  xinject focus <title-substr>        raise + focus a matching window
  xinject key <name> down|up|press    XTest key event (name is an X keysym)
  xinject sendkey <title> <name> down|up|press
                                      same, but addressed to the window with
                                      XSendEvent: no input focus needed, so an
                                      automated run never steals the user's
  xinject btn <1-3> down|up|click     XTest mouse button
  xinject move <dx> <dy> [n] [ms]      relative pointer motion, n times (sustained)

Exit status is non-zero on a bad command or a missing window, so a test script
can assert on it. Nothing here is game-specific; it is a general X11 tool.
"""

import ctypes
import os
import re
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

    _x11.XInternAtom.restype = ctypes.c_ulong
    _x11.XInternAtom.argtypes = [c_void_p, ctypes.c_char_p, ctypes.c_int]
    _x11.XSendEvent.restype = ctypes.c_int
    _x11.XSendEvent.argtypes = [c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_long, c_void_p]
    _x11.XGetInputFocus.restype = ctypes.c_int
    _x11.XGetInputFocus.argtypes = [c_void_p, ctypes.POINTER(ctypes.c_ulong),
                                    ctypes.POINTER(ctypes.c_int)]


ClientMessage = 33
SubstructureRedirectMask = 1 << 20
SubstructureNotifyMask = 1 << 19

KeyPress = 2
KeyRelease = 3
KeyPressMask = 1 << 0
KeyReleaseMask = 1 << 1


class _XClientMessageEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", c_void_p),
        ("window", ctypes.c_ulong),
        ("message_type", ctypes.c_ulong),
        ("format", ctypes.c_int),
        ("data", ctypes.c_long * 5),
    ]


class _XKeyEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", c_void_p),
        ("window", ctypes.c_ulong),
        ("root", ctypes.c_ulong),
        ("subwindow", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("x_root", ctypes.c_int),
        ("y_root", ctypes.c_int),
        ("state", ctypes.c_uint),
        ("keycode", ctypes.c_uint),
        ("same_screen", ctypes.c_int),
    ]


class _XEvent(ctypes.Union):
    _fields_ = [("xclient", _XClientMessageEvent), ("xkey", _XKeyEvent),
                ("pad", ctypes.c_long * 24)]


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


def _send_key_to(win, keycode, press):
    """Queue one synthetic KeyPress/KeyRelease addressed to `win` only.

    XSendEvent delivers the event straight to the window's client, so it does
    not need (and does not take) the X input focus -- unlike XTEST, which the
    server routes to whatever holds focus."""
    root = _x11.XDefaultRootWindow(_dpy)
    ev = _XEvent()
    ctypes.memset(ctypes.byref(ev), 0, ctypes.sizeof(ev))
    ev.xkey.type = KeyPress if press else KeyRelease
    ev.xkey.send_event = 1
    ev.xkey.display = _dpy
    ev.xkey.window = win
    ev.xkey.root = root
    ev.xkey.subwindow = 0
    ev.xkey.time = CurrentTime
    ev.xkey.x = 1
    ev.xkey.y = 1
    ev.xkey.x_root = 1
    ev.xkey.y_root = 1
    ev.xkey.state = 0
    ev.xkey.keycode = keycode
    ev.xkey.same_screen = 1
    _x11.XSendEvent(_dpy, win, 1, KeyPressMask | KeyReleaseMask, ctypes.byref(ev))


def do_sendkey(needle, name, action):
    """key() without focus: address the events to the matching window."""
    win = find_window(_x11.XDefaultRootWindow(_dpy), needle)
    if not win:
        print(f"xinject: no window matching '{needle}'", file=sys.stderr)
        return 4
    keysym = _x11.XStringToKeysym(name.encode())
    if not keysym:
        print(f"xinject: unknown keysym '{name}'", file=sys.stderr)
        return 3
    keycode = _x11.XKeysymToKeycode(_dpy, keysym)
    if not keycode:
        print(f"xinject: no keycode for '{name}'", file=sys.stderr)
        return 3
    if action in ("down", "press"):
        _send_key_to(win, keycode, True)
    if action in ("up", "press"):
        _send_key_to(win, keycode, False)
    if action not in ("down", "up", "press"):
        print("xinject: key action must be down|up|press", file=sys.stderr)
        return 3
    _x11.XFlush(_dpy)
    print(f"sendkey {name} {action} keycode {keycode} -> 0x{win:08x} (no focus change)")
    return 0


def do_btn(number, action):
    if action in ("down", "click"):
        _xtst.XTestFakeButtonEvent(_dpy, number, 1, CurrentTime)
    if action in ("up", "click"):
        _xtst.XTestFakeButtonEvent(_dpy, number, 0, CurrentTime)
    _x11.XFlush(_dpy)
    print(f"btn {number} {action}")
    return 0


# -- off-focus injection via the runtime's control file ---------------------
#
# XTEST needs the window focused and XSendEvent sticks keys under Wine, so key
# injection for automated runs goes through a small file the runtime polls
# (src/video/fb_present.c:fb_inject_poll). It writes the held virtual-key set
# there; no X input focus is touched.
INPUT_HOST = os.environ.get(
    "RECOMP_INPUT_HOST",
    os.path.expanduser("~/Games/scghost-prefix/pfx/drive_c/recomp-input.txt"))

_VK = {
    "space": 0x20, "return": 0x0D, "enter": 0x0D, "escape": 0x1B, "esc": 0x1B,
    "tab": 0x09, "backspace": 0x08, "shift": 0x10, "ctrl": 0x11,
    "control": 0x11, "alt": 0x12, "up": 0x26, "down": 0x28,
    "left": 0x25, "right": 0x27,
}
for _i in range(12):
    _VK["f%d" % (_i + 1)] = 0x70 + _i


def vk_of(name):
    n = name.lower()
    if n in _VK:
        return _VK[n]
    if len(n) == 1 and n.isalnum():
        return ord(n.upper())
    raise KeyError(name)


def _read_held():
    try:
        with open(INPUT_HOST) as handle:
            text = handle.read()
    except OSError:
        return set()
    return {int(tok, 16) for tok in re.findall(r"[0-9a-fA-F]{1,2}", text)}


def _write_held(held):
    tmp = INPUT_HOST + ".tmp"
    with open(tmp, "w") as handle:
        handle.write(" ".join("%02X" % v for v in sorted(held)))
    os.replace(tmp, INPUT_HOST)      # atomic: a poller never sees a blank set


def do_keyfile(name, action):
    try:
        vk = vk_of(name)
    except KeyError:
        print(f"xinject: no VK mapping for '{name}'", file=sys.stderr)
        return 3
    if action not in ("down", "up", "press"):
        print("xinject: key action must be down|up|press", file=sys.stderr)
        return 3
    held = _read_held()
    if action == "down":
        held.add(vk)
        _write_held(held)
    elif action == "up":
        held.discard(vk)
        _write_held(held)
    else:  # press: a real held window so the poller observes the edge
        held.add(vk)
        _write_held(held)
        time.sleep(0.15)
        held.discard(vk)
        _write_held(held)
    print(f"keyfile {name} {action} vk=0x{vk:02X} held={sorted(held)}")
    return 0


def do_activate(needle):
    """Ask the window manager to activate a window (EWMH _NET_ACTIVE_WINDOW).

    XSetInputFocus alone is not enough: a focus-policy WM (mutter) reverts it,
    so the window never becomes the active window and never receives WM_KEYDOWN
    -- mouse motion works, keyboard does not. A pager-sourced activation
    request is what the WM actually honours."""
    win = find_window(_x11.XDefaultRootWindow(_dpy), needle)
    if not win:
        print(f"xinject: no window matching '{needle}'", file=sys.stderr)
        return 4
    root = _x11.XDefaultRootWindow(_dpy)
    atom = _x11.XInternAtom(_dpy, b"_NET_ACTIVE_WINDOW", 0)
    ev = _XEvent()
    ctypes.memset(ctypes.byref(ev), 0, ctypes.sizeof(ev))
    ev.xclient.type = ClientMessage
    ev.xclient.send_event = 1
    ev.xclient.display = _dpy
    ev.xclient.window = win
    ev.xclient.message_type = atom
    ev.xclient.format = 32
    ev.xclient.data[0] = 2  # source indication: pager
    ev.xclient.data[1] = CurrentTime
    ev.xclient.data[2] = 0
    _x11.XSendEvent(_dpy, root, 0,
                    SubstructureRedirectMask | SubstructureNotifyMask, ctypes.byref(ev))
    _x11.XRaiseWindow(_dpy, win)
    _x11.XSetInputFocus(_dpy, win, RevertToParent, CurrentTime)
    _x11.XFlush(_dpy)
    print(f"activated 0x{win:08x}")
    return 0


def do_getfocus():
    win = ctypes.c_ulong()
    revert = ctypes.c_int()
    _x11.XGetInputFocus(_dpy, ctypes.byref(win), ctypes.byref(revert))
    _x11.XFlush(_dpy)
    name = window_name(win.value)
    print(f"focus 0x{win.value:08x} revert={revert.value} name='{name}'")
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
    elif cmd == "activate" and len(argv) >= 3:
        return do_activate(argv[2])
    elif cmd == "getfocus":
        return do_getfocus()
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
    elif cmd == "keyfile" and len(argv) >= 4:
        return do_keyfile(argv[2], argv[3])
    elif cmd == "sendkey" and len(argv) >= 5:
        return do_sendkey(argv[2], argv[3], argv[4])
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
