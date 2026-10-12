#!/usr/bin/env python3
"""Framebuffer capture tooling: convert the runtime's F12 BMP dumps to PNG and
compare two captures.

The runtime writes a 24-bit bottom-up BMP (see xbox_FramebufferDumpBmp in
refs/xboxrecomp/src/video/fb_present.c). There is no PIL or ImageMagick on this
host, so PNG encoding is done with stdlib zlib/struct.

Usage:
  fbtool.py png  <in.bmp> <out.png>
  fbtool.py diff <a.bmp> <b.bmp> [--tol N]   # mean abs diff + % pixels over tol
"""
import struct
import sys
import zlib


def load_bmp(path):
    """Return (width, height, rgb_bytes) top-down, 3 bytes/px."""
    with open(path, "rb") as handle:
        data = handle.read()
    if data[:2] != b"BM":
        raise ValueError(f"{path}: not a BMP")
    offset = struct.unpack_from("<I", data, 10)[0]
    width = struct.unpack_from("<i", data, 18)[0]
    height = struct.unpack_from("<i", data, 22)[0]
    bpp = struct.unpack_from("<H", data, 28)[0]
    if bpp not in (24, 32):
        raise ValueError(f"{path}: unsupported {bpp} bpp")
    bpp_bytes = bpp // 8
    row = ((width * bpp_bytes) + 3) & ~3
    top_down = height < 0
    height = abs(height)
    out = bytearray(width * height * 3)
    for y in range(height):
        src_y = y if top_down else height - 1 - y
        base = offset + src_y * row
        for x in range(width):
            s = base + x * bpp_bytes
            d = (y * width + x) * 3
            out[d + 0] = data[s + 2]
            out[d + 1] = data[s + 1]
            out[d + 2] = data[s + 0]
    return width, height, bytes(out)


def write_png(path, width, height, rgb):
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]

    def chunk(typ, payload):
        return (struct.pack(">I", len(payload)) + typ + payload +
                struct.pack(">I", zlib.crc32(typ + payload) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    with open(path, "wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n")
        handle.write(chunk(b"IHDR", ihdr))
        handle.write(chunk(b"IDAT", zlib.compress(bytes(raw), 6)))
        handle.write(chunk(b"IEND", b""))


def load_png(path):
    """Read a PNG written by write_png (8-bit RGB, filter 0 rows only)."""
    with open(path, "rb") as handle:
        data = handle.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not a PNG")
    pos, idat, width, height = 8, bytearray(), 0, 0
    while pos < len(data):
        length, typ = struct.unpack_from(">I4s", data, pos)
        payload = data[pos + 8:pos + 8 + length]
        if typ == b"IHDR":
            width, height, depth, color = struct.unpack_from(">IIBB", payload)
            if (depth, color) != (8, 2):
                raise ValueError(f"{path}: only 8-bit RGB supported")
        elif typ == b"IDAT":
            idat += payload
        pos += 12 + length
    raw = zlib.decompress(bytes(idat))
    stride = width * 3
    out = bytearray()
    for y in range(height):
        row = raw[y * (stride + 1):(y + 1) * (stride + 1)]
        if row[0] != 0:
            raise ValueError(f"{path}: row filter {row[0]} unsupported")
        out += row[1:]
    return width, height, bytes(out)


def load_image(path):
    return load_png(path) if path.lower().endswith(".png") else load_bmp(path)


def region_diff(a, b, box):
    """Mean abs channel difference of two loaded images inside box=(x0,y0,x1,y1)."""
    (wa, ha, pa), (wb, hb, pb) = a, b
    if (wa, ha) != (wb, hb):
        raise ValueError(f"size mismatch {wa}x{ha} vs {wb}x{hb}")
    x0, y0, x1, y1 = box
    total = 0
    for y in range(y0, y1):
        base = (y * wa + x0) * 3
        ra, rb = pa[base:base + (x1 - x0) * 3], pb[base:base + (x1 - x0) * 3]
        total += sum(abs(p - q) for p, q in zip(ra, rb))
    return total / ((x1 - x0) * (y1 - y0) * 3)


def diff(a, b, tol=8):
    wa, ha, pa = load_bmp(a)
    wb, hb, pb = load_bmp(b)
    if (wa, ha) != (wb, hb):
        raise ValueError(f"size mismatch {wa}x{ha} vs {wb}x{hb}")
    total = 0
    over = 0
    n = wa * ha * 3
    for i in range(n):
        d = abs(pa[i] - pb[i])
        total += d
        if d > tol:
            over += 1
    return total / n, over * 100.0 / n


def main(argv):
    if len(argv) < 4:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "png":
        w, h, rgb = load_bmp(argv[2])
        write_png(argv[3], w, h, rgb)
        print(f"{argv[2]} -> {argv[3]} ({w}x{h})")
        return 0
    if cmd == "diff":
        tol = 8
        if "--tol" in argv:
            tol = int(argv[argv.index("--tol") + 1])
        mean, pct = diff(argv[2], argv[3], tol)
        print(f"mean_abs={mean:.2f} pct_over_tol={pct:.2f}% (tol={tol})")
        return 0
    print(f"unknown command {cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))