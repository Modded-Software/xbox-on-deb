#!/usr/bin/env python3
"""Append a payload + footer to the installer PE."""
import argparse
import struct
import sys
import zlib
from pathlib import Path

MAGIC_PAY = b"SGHRPAY1"
MAGIC_FOOT = b"SGHRPKG1"
VERSION = 1


def crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def pack(setup: Path, out: Path, entries):
    body = bytearray()
    body += MAGIC_PAY
    body += struct.pack("<II", VERSION, len(entries))
    for kind, dest, src in entries:
        data = src.read_bytes()
        path = dest.replace("\\", "/").encode("utf-8")
        if path.startswith(b"/") or b".." in path.split(b"/") or b":" in path:
            raise SystemExit(f"bad path: {dest}")
        body += struct.pack("<BBHI", kind, 0, len(path), crc32(data))
        body += struct.pack("<Q", len(data))
        body += path
        body += data
    pe = setup.read_bytes()
    footer = MAGIC_FOOT + struct.pack("<IQQI", VERSION, len(pe), len(body), crc32(body))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(pe + bytes(body) + footer)
    print(f"packed {out} ({out.stat().st_size} bytes, {len(entries)} entries)")


def verify(path: Path) -> int:
    data = path.read_bytes()
    if len(data) < 32 or data[-32:-24] != MAGIC_FOOT:
        print("no footer", file=sys.stderr)
        return 1
    version, offset, size, expect = struct.unpack_from("<IQQI", data[-24:])
    if version != VERSION or offset + size + 32 != len(data):
        print("bad footer geometry", file=sys.stderr)
        return 1
    body = data[offset:offset + size]
    got = crc32(body)
    if got != expect or not body.startswith(MAGIC_PAY):
        print(f"crc mismatch {got:08x} != {expect:08x}", file=sys.stderr)
        return 1
    count = struct.unpack_from("<I", body, 12)[0]
    print(f"ok version={version} entries={count} payload={size}")
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--setup", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--entry", action="append", default=[],
                   help="kind|dest|src  kind=1 install, 2 asset")
    p.add_argument("--verify", type=Path)
    args = p.parse_args()
    if args.verify:
        raise SystemExit(verify(args.verify))
    entries = []
    for item in args.entry:
        kind_s, dest, src = item.split("|", 2)
        entries.append((int(kind_s), dest, Path(src)))
    pack(args.setup, args.out, entries)


if __name__ == "__main__":
    main()
