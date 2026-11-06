#!/usr/bin/env python3
"""Guest-screen probes for the XP demo recorder (scripts/31-xp-demo.sh).

Two checks, both on a QEMU monitor screendump (binary PPM, P6):

  ready PPM   1 when the XP desktop is up (taskbar visible at the bottom)
  alive PPM   1 while the installer window is on screen, 0 when it is gone

The installer window is a large, mostly black artwork panel in the middle of
the screen; when it exits the desktop (bright grass/sky) shows through. So the
liveness check samples a grid in the middle and counts dark samples.

Exit code is always 0; the answer is printed as 0/1.
"""
import sys


def read_ppm(path):
    with open(path, "rb") as fh:
        data = fh.read()
    if not data.startswith(b"P6"):
        raise SystemExit("not a binary PPM")
    fields = []
    i = 2
    while len(fields) < 3:
        while data[i:i + 1].isspace():
            i += 1
        if data[i:i + 1] == b"#":
            while data[i:i + 1] not in (b"\n", b""):
                i += 1
            continue
        start = i
        while not data[i:i + 1].isspace():
            i += 1
        fields.append(int(data[start:i]))
    i += 1
    w, h, maxval = fields
    px = data[i:]
    return w, h, maxval, px


def pixel(px, w, x, y):
    o = (y * w + x) * 3
    return px[o], px[o + 1], px[o + 2]


def main():
    what, path = sys.argv[1], sys.argv[2]
    w, h, _max, px = read_ppm(path)
    if what == "ready":
        # The XP taskbar is a blue strip along the bottom edge; the desktop
        # above it is bright. Both must be present.
        bar = [pixel(px, w, x, h - 8) for x in range(20, w - 20, 40)]
        blue = sum(1 for r, g, b in bar if b > 80 and b > r + 20 and g < b)
        desk = [pixel(px, w, x, h // 2) for x in range(w // 8, w * 7 // 8, 32)]
        bright = sum(1 for r, g, b in desk if max(r, g, b) > 60)
        print(1 if blue > len(bar) * 0.7 and bright > len(desk) * 0.5 else 0)
        return
    # alive: a grid over the middle of the guest screen.
    dark = 0
    total = 0
    for fy in range(30, 80, 7):
        for fx in range(20, 80, 7):
            r, g, b = pixel(px, w, w * fx // 100, h * fy // 100)
            total += 1
            if max(r, g, b) < 70:
                dark += 1
    print(1 if dark >= total // 3 else 0)


main()
