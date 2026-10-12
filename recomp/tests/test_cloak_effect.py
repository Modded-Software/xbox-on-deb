#!/usr/bin/env python3
"""Integration test: the cloak/refraction effect renders correctly on d-pad left.

Same path as the a-mash test -- reach the first mission and into gameplay -- then
hold d-pad left (Left arrow in the default KBM layout) to trigger the cloak
ability, wait for the runtime's `[CLOAK] active` marker (emitted when the
`cloak*.xvu/.xpu` shaders load; see nv2a_pb_exec.c / nv2a_gpu_d3d11.cpp), then
F12-capture the framebuffer and check the image (check_cloak_frame):

  * HUD intact: the radar and ammo panel match the pre-cloak capture. The
    async-flip regression dropped the whole HUD while cloaked.
  * character present: the region where Nova stands differs from
    baselines/cloak/empty-corridor.png (the broken render: corridor, no Nova).

Captures land in /tmp/opencode/cloak-{before,after}.bmp plus cloak-after.png.

    recomp/tests/run.py --user-state --only cloak

Score captures offline, or self-check against the committed baselines
(cloaked-good.png must pass, empty-corridor.png must fail):

    test_cloak_effect.py <after.bmp|png> <before.bmp|png>
    test_cloak_effect.py --self-check
"""
import os
import shutil
import sys
import time

import fbtool

HERE = os.path.dirname(os.path.abspath(__file__))
BASELINES = os.path.join(HERE, "baselines", "cloak")
EMPTY_CORRIDOR = os.path.join(BASELINES, "empty-corridor.png")
CLOAKED_GOOD = os.path.join(BASELINES, "cloaked-good.png")
OUT_BEFORE = "/tmp/opencode/cloak-before.bmp"
OUT_AFTER = "/tmp/opencode/cloak-after.bmp"

# 1920x1080 regions (x0, y0, x1, y1). The energy bar and objective banner change
# when the cloak engages, so only the radar and ammo panel are compared.
HUD_REGIONS = {"radar": (130, 750, 470, 1025), "ammo": (1470, 875, 1745, 1000)}
# Nova idles/steps around the screen centre while cloaked (seen up to ~x1270),
# so the box spans her whole range; a narrow torso box missed her once.
CHARACTER = (640, 330, 1400, 1040)
# Calibrated on 6 good / 3 broken captures (2026-10-11): HUD vs before is
# <=0.33 good, 22.2 / 9.7 broken; character vs empty corridor is 1.41-1.92
# good, exactly 0.00 broken (the broken render is deterministic).
HUD_MAX = 3.0
CHARACTER_MIN = 0.5


def check_cloak_frame(after, before):
    """Return a list of failure strings for a cloaked capture (empty = good)."""
    a, b = fbtool.load_image(after), fbtool.load_image(before)
    failures = []
    for name, box in HUD_REGIONS.items():
        score = fbtool.region_diff(a, b, box)
        print(f"  {name} vs pre-cloak: {score:.2f} (max {HUD_MAX})")
        if score > HUD_MAX:
            failures.append(f"HUD {name} missing/changed while cloaked ({score:.1f})")
    score = fbtool.region_diff(a, fbtool.load_image(EMPTY_CORRIDOR), CHARACTER)
    print(f"  character vs empty corridor: {score:.2f} (min {CHARACTER_MIN})")
    if score < CHARACTER_MIN:
        failures.append(f"character missing while cloaked ({score:.2f})")
    return failures


def self_check():
    """The good baseline must pass and the broken one must fail."""
    good = check_cloak_frame(CLOAKED_GOOD, CLOAKED_GOOD)
    assert not good, f"good baseline rejected: {good}"
    broken = check_cloak_frame(EMPTY_CORRIDOR, CLOAKED_GOOD)
    assert len(broken) == 3, f"broken baseline not fully rejected: {broken}"
    print("self-check OK")


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-check"]:
        self_check()
        sys.exit(0)
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    problems = check_cloak_frame(sys.argv[1], sys.argv[2])
    print("\n".join(problems) or "cloak frame OK")
    sys.exit(1 if problems else 0)


from framework import CAPTURE as FB_BMP, Game, test


def _grab(g, dest):
    """F12-capture the framebuffer, copy the dump to `dest`, return its hash."""
    digest = g.capture_hash()
    if digest and os.path.exists(FB_BMP):
        shutil.copyfile(FB_BMP, dest)
    return digest


@test("cloak refraction effect renders on d-pad left (HUD + character)")
def cloak_effect(g: Game):
    assert g.goto_gameplay(key="space", gap=2.0, timeout=240.0), \
        "never reached gameplay (level .nhc, world shaders, quiet streaming)"
    time.sleep(2.0)                      # let the mission settle
    before = _grab(g, OUT_BEFORE)
    offset = g.log_offset()
    g.focus()
    g.key("left", "down")                # hold d-pad left -> cloak ability
    try:
        assert g.wait_log_line("[CLOAK] active", timeout=8.0, offset=offset), \
            "no [CLOAK] active marker after d-pad left"
        time.sleep(4.0)                  # let the cloak animation fully settle
        after = _grab(g, OUT_AFTER)
        time.sleep(4.0)                  # keep the effect up a while before exiting
    finally:
        g.key("left", "up")
    assert before and after, "framebuffer capture failed (F12 dump missing)"
    png = OUT_AFTER.rsplit(".", 1)[0] + ".png"
    width, height, rgb = fbtool.load_bmp(OUT_AFTER)
    fbtool.write_png(png, width, height, rgb)
    # Keep every run's frame next to its runtime log, so an intermittent failure
    # can still be looked at after later runs overwrite /tmp.
    kept = os.path.join(HERE, "..", "..", "logs", time.strftime("cloak-%Y%m%d-%H%M%S.png"))
    shutil.copyfile(png, kept)
    print(f"  captured {png} ({width}x{height}), kept {os.path.normpath(kept)}")
    problems = check_cloak_frame(OUT_AFTER, OUT_BEFORE)
    assert not problems, "; ".join(problems)
