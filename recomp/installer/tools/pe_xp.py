#!/usr/bin/env python3
"""Mark PE binaries as Windows XP compatible.

Zig's linker writes subsystem version 6.0 into the optional header. Windows XP
refuses to start an image whose subsystem major version is above 5, so setup
and uninstaller images built for the XP demo are rewritten to 5.1 here.

    pe_xp.py FILE [FILE...]
"""
import struct
import sys


def patch(path):
    with open(path, "r+b") as f:
        data = bytearray(f.read())
        if data[:2] != b"MZ":
            raise SystemExit(f"{path}: not a PE image")
        e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
        if data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
            raise SystemExit(f"{path}: no PE signature")
        opt = e_lfanew + 4 + 20
        magic = struct.unpack_from("<H", data, opt)[0]
        if magic not in (0x10B, 0x20B):
            raise SystemExit(f"{path}: unknown optional header magic {magic:#x}")
        old = struct.unpack_from("<HH", data, opt + 48)
        struct.pack_into("<HH", data, opt + 48, 5, 1)
        if old == (5, 1):
            print(f"{path}: already 5.1")
        else:
            print(f"{path}: subsystem {old[0]}.{old[1]} -> 5.1")
        f.seek(0)
        f.write(data)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for p in sys.argv[1:]:
        patch(p)
