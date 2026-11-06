#!/usr/bin/env python3
"""Build res/installer-assets/ghost.ico from the archive key art.

The icon is a square crop of the Nova face key art (the same image family the
installer uses for its splash pages).

The ICO is written by hand instead of Pillow's ICO saver: every entry is an
uncompressed 32bpp BMP with an AND mask, because Windows XP's shell cannot read
the PNG-compressed entries Pillow emits for large sizes.

Usage: uv run python recomp/installer/tools/make_icon.py [out.ico]
"""
import io
import struct
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError as exc:
    raise SystemExit(
        "Pillow is required: uv pip install pillow"
    ) from exc

ROOT = Path(__file__).resolve().parent.joinpath("..", "..", "..").resolve()
SRC = ROOT / "res/starcraft-ghost-archive/images/keyart-nova-face.jpg"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "res/installer-assets/ghost.ico"

CROP = (0, 165, 465, 630)  # Nova's face, left side of the key art
SIZES = [16, 24, 32, 48, 64, 128]


def bmp_entry(img):
    """32bpp bottom-up BGRA DIB plus a 1bpp AND mask, as stored in an ICO."""
    w, h = img.size
    px = img.convert("RGBA").load()
    rows = []
    for y in range(h - 1, -1, -1):
        row = bytearray()
        for x in range(w):
            r, g, b, a = px[x, y]
            row += bytes((b, g, r, a))
        rows.append(bytes(row))
    pixels = b"".join(rows)
    mask_stride = ((w + 31) // 32) * 4
    mask = bytes(mask_stride * h)
    header = struct.pack(
        "<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, len(pixels) + len(mask), 0, 0, 0, 0
    )
    return header + pixels + mask


if not SRC.is_file():
    raise SystemExit(f"missing key art: {SRC}")

art = Image.open(SRC).convert("RGB").crop(CROP)
images = [art.resize((s, s), Image.LANCZOS) for s in SIZES]
blobs = [bmp_entry(im) for im in images]

out = io.BytesIO()
out.write(struct.pack("<HHH", 0, 1, len(blobs)))
offset = 6 + 16 * len(blobs)
for im, blob in zip(images, blobs):
    w, h = im.size
    out.write(struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, 1, 32, len(blob), offset))
    offset += len(blob)
for blob in blobs:
    out.write(blob)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_bytes(out.getvalue())
print(f"wrote {OUT} ({len(out.getvalue())} bytes, sizes {SIZES})")
