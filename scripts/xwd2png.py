#!/usr/bin/env python3
"""Convert an XWD (X Window Dump) file to PNG using Pillow.

Only handles TrueColor/DirectColor dumps, which is what XWayland produces.
Usage: xwd2png.py input.xwd output.png
"""
import struct
import sys
from PIL import Image

HEADER_FMT = ">25I"
HEADER_SIZE = struct.calcsize(HEADER_FMT)

(
    header_size, file_version, pixmap_format, pixmap_depth, pixmap_width,
    pixmap_height, xoffset, byte_order, bitmap_unit, bitmap_bit_order,
    bitmap_pad, bits_per_pixel, bytes_per_line, visual_class, red_mask,
    green_mask, blue_mask, bits_per_rgb, colormap_entries, ncolors,
    window_width, window_height, window_x, window_y, window_bdrwidth,
) = struct.unpack(HEADER_FMT, open(sys.argv[1], "rb").read(HEADER_SIZE))

assert file_version == 7, f"unsupported XWD version {file_version}"
assert pixmap_format == 2, f"unsupported pixmap_format {pixmap_format} (need ZPixmap)"
assert visual_class in (4, 5), f"unsupported visual_class {visual_class} (need TrueColor)"

with open(sys.argv[1], "rb") as fh:
    data = fh.read()

pixel_offset = header_size + ncolors * 12
data = data[pixel_offset:]
if (red_mask, green_mask, blue_mask) == (0xFF0000, 0xFF00, 0xFF):
    rawmode = "BGRX"  # little-endian: bytes B,G,R,X in memory
elif (red_mask, green_mask, blue_mask) == (0xFF, 0xFF00, 0xFF0000):
    rawmode = "RGBX"
else:
    raise SystemExit(f"unhandled masks R={red_mask:#x} G={green_mask:#x} B={blue_mask:#x}")

img = Image.frombytes("RGBX", (pixmap_width, pixmap_height), data, "raw", rawmode, bytes_per_line)
img.convert("RGB").save(sys.argv[2])
print(f"{sys.argv[2]}: {pixmap_width}x{pixmap_height} depth={pixmap_depth} bpp={bits_per_pixel}")
