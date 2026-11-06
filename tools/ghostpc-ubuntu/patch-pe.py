#!/usr/bin/env python3
"""Clear ASLR/NX flags on a PE32 so Wine loads it at its preferred base.

GhostPC must load at 0x10000000: Ghost.exe wants 0x00400000, and forcing the
game image to relocate breaks its absolute pointers. lld's /DYNAMICBASE cannot
be turned off through the zig wrapper, so patch DllCharacteristics after link
(upstream build.bat uses /DYNAMICBASE:NO /NXCOMPAT:NO /FIXED for the same
reason).
"""
import struct
import sys

DYNAMIC_BASE = 0x0040
NX_COMPAT = 0x0100


def main(path: str) -> int:
    with open(path, "rb") as f:
        data = bytearray(f.read())
    if data[:2] != b"MZ":
        print(f"{path}: not a PE file", file=sys.stderr)
        return 1
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    if data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
        print(f"{path}: missing PE signature", file=sys.stderr)
        return 1
    opt = e_lfanew + 24
    magic = struct.unpack_from("<H", data, opt)[0]
    if magic != 0x10B:
        print(f"{path}: not PE32 (magic 0x{magic:X})", file=sys.stderr)
        return 1
    dllchar_off = opt + 0x46
    before = struct.unpack_from("<H", data, dllchar_off)[0]
    after = before & ~(DYNAMIC_BASE | NX_COMPAT)
    struct.pack_into("<H", data, dllchar_off, after)
    with open(path, "wb") as f:
        f.write(data)
    print(f"patched {path}: DllCharacteristics 0x{before:04X} -> 0x{after:04X}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} GhostPC.exe", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
