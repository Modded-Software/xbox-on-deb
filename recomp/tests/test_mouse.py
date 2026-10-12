#!/usr/bin/env python3
"""Mouse tests at the input layer.

The menu polls the pad sparsely, so relative motion injected there coalesces
across polls and cannot be measured precisely; this only requires that motion
*reaches* the right stick. Direction, scale and in-game responsiveness are
checked once a mission is running, in test_zzz_gameplay.py, where the title
polls every frame.
"""
from framework import Game, test


@test("relative mouse motion reaches the right stick")
def mouse_reaches_stick(g: Game):
    sample = g.mouse_move(200, 0)
    assert sample, "no [KBM] mouse trace after injecting motion"
    assert sample["dx"] != 0 or sample["rx"] != 0, f"motion vanished: {sample}"
