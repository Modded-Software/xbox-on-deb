#!/usr/bin/env python3
"""Remove Cxbx's primary-monitor window clamp from cxbx.exe.

`WndMain::ResizeWindow` clamps its window to `GetDesktopWindow()` (the primary
monitor). When the primary is smaller than the configured resolution (e.g. a
portrait 1080-wide panel with VideoResolution=1920x1080), the window becomes
square and the image is distorted.

The clamp is two conditional branches:

    42a1e1: 3b d1        cmp  %ecx,%edx    ; m_w vs dWidth
    42a1e3: 7e 06        jle  0x42a1eb     ; if m_w <= dWidth skip
    42a1e5: 89 0f        mov  %ecx,(%edi)  ; m_w = dWidth
    42a1e7: 89 4c 24 0c  mov  %ecx,0xc(%esp)
    42a1eb: 8b 3e        mov  (%esi),%edi  ; m_h
    42a1ed: 3b f8        cmp  %eax,%edi
    42a1ef: 7e 04        jle  0x42a1f5
    42a1f1: 89 06        mov  %eax,(%esi)  ; m_h = dHeight
    42a1f3: 8b f8        mov  %eax,%edi

Changing the two `jle` (0x7E) opcodes to `jmp` (0xEB) makes both clamps skip,
so Cxbx creates the configured window size regardless of monitor geometry.

Usage: patch_cxbx_clamp.py <cxbx.exe>
"""
import shutil
import sys

PATTERN = bytes.fromhex("3bd17e06890f894c240c8b3e3bf87e0489068bf8")
JLE = 0x7E
JMP = 0xEB


def main():
    exe = sys.argv[1]
    backup = exe + ".orig"
    with open(exe, "rb") as f:
        data = bytearray(f.read())

    hits = []
    start = 0
    while True:
        i = data.find(PATTERN, start)
        if i == -1:
            break
        hits.append(i)
        start = i + 1

    if len(hits) != 1:
        raise SystemExit(f"expected exactly 1 clamp pattern, found {len(hits)}: "
                         f"{[hex(h) for h in hits]}")

    off = hits[0]
    if data[off + 2] != JLE or data[off + 14] != JLE:
        raise SystemExit("pattern matched but opcodes are not 0x7E; aborting")

    shutil.copyfile(exe, backup)
    data[off + 2] = JMP
    data[off + 14] = JMP
    with open(exe, "wb") as f:
        f.write(data)

    print(f"patched clamp at file offset 0x{off:x} (2x jle->jmp), backup: {backup}")


if __name__ == "__main__":
    main()
