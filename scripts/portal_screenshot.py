#!/usr/bin/env python3
"""Take a screenshot via the XDG desktop portal (works for GPU/DXVK windows
that xwd cannot read). Usage: portal_screenshot.py OUT.png"""
import shutil
import sys
import urllib.parse

import gi

gi.require_version("Gio", "2.0")
from gi.repository import GLib, Gio  # noqa: E402

BUS_NAME = "org.freedesktop.portal.Desktop"
OBJ_PATH = "/org/freedesktop/portal/desktop"
IFACE = "org.freedesktop.portal.Screenshot"
REQ_IFACE = "org.freedesktop.portal.Request"

result = {}
loop = GLib.MainLoop()


def on_response(conn, sender, path, iface, signal, params, user_data):
    code, results = params.unpack()
    result["code"] = code
    result["uri"] = results.get("uri")
    loop.quit()


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/opencode/portal_shot.png"
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    bus.signal_subscribe(BUS_NAME, REQ_IFACE, "Response", None, None,
                         Gio.DBusSignalFlags.NONE, on_response, None)
    args = GLib.Variant("(sa{sv})", ("", {"interactive": GLib.Variant("b", False)}))
    try:
        bus.call_sync(BUS_NAME, OBJ_PATH, IFACE, "Screenshot", args, None,
                      Gio.DBusCallFlags.NONE, -1, None)
    except GLib.Error as err:
        raise SystemExit(f"portal Screenshot call failed: {err.message}")

    GLib.timeout_add(20000, lambda: (loop.quit(), False)[1])
    loop.run()

    if result.get("code") != 0 or not result.get("uri"):
        raise SystemExit(f"screenshot failed: {result}")
    src = urllib.parse.unquote(urllib.parse.urlparse(result["uri"]).path)
    shutil.copyfile(src, out_path)
    print(f"saved {out_path}")


if __name__ == "__main__":
    main()
