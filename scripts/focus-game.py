#!/usr/bin/env python3
"""Give the game window keyboard focus.

A scripted launch has no desktop user timestamp, so mutter refuses to hand the
window focus and Wine (WM_HINTS input=False + WM_TAKE_FOCUS) never receives key
events. Mouse still works because it goes through the pointer. This finds the
window by name, asks the WM to activate it, then sets the X input focus and
sends WM_TAKE_FOCUS. Exits 1 when the window is not there yet.
"""
import ctypes
import sys
import time

TITLE = "StarCraft: Ghost"


class XClientMessageEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("message_type", ctypes.c_ulong),
        ("format", ctypes.c_int),
        ("data", ctypes.c_long * 5),
    ]


x11 = ctypes.CDLL("libX11.so.6")
x11.XOpenDisplay.restype = ctypes.c_void_p
x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
x11.XDefaultRootWindow.restype = ctypes.c_ulong
x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
x11.XInternAtom.restype = ctypes.c_ulong
x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
x11.XQueryTree.argtypes = [
    ctypes.c_void_p, ctypes.c_ulong,
    ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
    ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
    ctypes.POINTER(ctypes.c_uint),
]
x11.XFetchName.argtypes = [
    ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_char_p)
]
x11.XFree.argtypes = [ctypes.c_void_p]
x11.XSendEvent.argtypes = [
    ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_long, ctypes.c_void_p
]
x11.XRaiseWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
x11.XSetInputFocus.argtypes = [
    ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong
]
x11.XFlush.argtypes = [ctypes.c_void_p]


def find_window(display, root, depth=0):
    root_ret = ctypes.c_ulong()
    parent_ret = ctypes.c_ulong()
    children = ctypes.POINTER(ctypes.c_ulong)()
    count = ctypes.c_uint()
    if not x11.XQueryTree(
        display, root, ctypes.byref(root_ret), ctypes.byref(parent_ret),
        ctypes.byref(children), ctypes.byref(count)
    ):
        return None
    found = None
    for i in range(count.value):
        win = children[i]
        name = ctypes.c_char_p()
        if x11.XFetchName(display, win, ctypes.byref(name)) and name.value:
            if TITLE.encode() in name.value:
                found = win
                x11.XFree(name)
                break
            x11.XFree(name)
        if depth < 4:
            found = find_window(display, win, depth + 1)
            if found:
                break
    if children:
        x11.XFree(children)
    return found


def main():
    display = x11.XOpenDisplay(None)
    if not display:
        return 1
    root = x11.XDefaultRootWindow(display)
    win = find_window(display, root)
    if not win:
        return 1

    net_active = x11.XInternAtom(display, b"_NET_ACTIVE_WINDOW", 0)
    protocols = x11.XInternAtom(display, b"WM_PROTOCOLS", 0)
    take_focus = x11.XInternAtom(display, b"WM_TAKE_FOCUS", 0)

    ev = XClientMessageEvent()
    ev.type = 33
    ev.window = win
    ev.message_type = net_active
    ev.format = 32
    ev.data[0] = 2
    x11.XSendEvent(display, root, 0, 0x180000 | 0x80000, ctypes.byref(ev))

    x11.XRaiseWindow(display, win)
    x11.XSetInputFocus(display, win, 1, 0)

    ev.window = win
    ev.message_type = protocols
    ev.data[0] = take_focus
    ev.data[1] = 0
    x11.XSendEvent(display, win, 0, 0, ctypes.byref(ev))
    x11.XFlush(display)
    time.sleep(0.2)
    print("focused 0x%x" % win)
    return 0


sys.exit(main())
