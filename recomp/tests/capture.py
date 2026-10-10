#!/usr/bin/env python3
"""Capture framebuffer frames from the USER profile for render inspection and
regression comparison.

Always runs the user entry point (scripts/18-launch-user.sh, 1280x720 KBM), the
same configuration a human plays, so captures are representative.

Usage:
  python recomp/tests/capture.py --tag NAME [--frames 8] [--interval 6]
  python recomp/tests/capture.py --diff TAG_A TAG_B   # compare two capture sets

Captures land in recomp/tests/baselines/captures/<tag>/NNN.bmp with an
equivalent .png (see fbtool.py). The diff reports mean absolute pixel error and
the percentage of pixels over a tolerance, per frame pair.
"""
import argparse
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from recomp.tests import framework as fw
from recomp.tests import fbtool

CAPTURES = os.path.join(HERE, "baselines", "captures")


def capture(tag, frames, interval):
    out = os.path.join(CAPTURES, tag)
    os.makedirs(out, exist_ok=True)
    game = fw.Game(attach=False, kbm=True, user_state=True, boot_timeout=150)
    game.start()
    results = []
    try:
        for i in range(frames):
            time.sleep(interval)
            digest = game.capture_hash(timeout=8.0)
            bmp = os.path.join(out, f"{i:03d}.bmp")
            png = os.path.join(out, f"{i:03d}.png")
            try:
                shutil.copy(fw.CAPTURE, bmp)
                w, h, rgb = fbtool.load_bmp(bmp)
                fbtool.write_png(png, w, h, rgb)
                size = f"{w}x{h}"
            except OSError as exc:
                size = f"copyfail:{exc}"
            line = f"{i:03d} hash={digest} {size}"
            print(line, flush=True)
            results.append(line)
    finally:
        game.stop()
    with open(os.path.join(out, "index.txt"), "w") as handle:
        handle.write("\n".join(results) + "\n")
    return out


def diff(tag_a, tag_b):
    a_dir = os.path.join(CAPTURES, tag_a)
    b_dir = os.path.join(CAPTURES, tag_b)
    names = sorted(n[:-4] for n in os.listdir(a_dir) if n.endswith(".bmp"))
    worst = 0.0
    for name in names:
        pa = os.path.join(a_dir, name + ".bmp")
        pb = os.path.join(b_dir, name + ".bmp")
        if not os.path.exists(pb):
            print(f"{name}: missing in {tag_b}")
            continue
        mean, pct = fbtool.diff(pa, pb)
        worst = max(worst, pct)
        print(f"{name}: mean_abs={mean:.2f} pct_over_tol={pct:.2f}%")
    print(f"worst pct_over_tol={worst:.2f}%")
    return worst


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="capture set name")
    parser.add_argument("--frames", type=int, default=8)
    parser.add_argument("--interval", type=float, default=6.0)
    parser.add_argument("--diff", nargs=2, metavar=("A", "B"))
    args = parser.parse_args()
    if args.diff:
        diff(args.diff[0], args.diff[1])
        return 0
    if not args.tag:
        parser.error("--tag or --diff required")
    capture(args.tag, args.frames, args.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())