#!/usr/bin/env python3
"""Mouse tests at the input layer.

The menu polls the pad sparsely, so these only require that relative motion
*reaches* the right stick; direction and in-game responsiveness are checked
once a mission is running, in test_zzz_gameplay.py, where the title polls
every frame.
"""
from framework import Game, test


@test("relative mouse motion reaches the right stick")
def mouse_reaches_stick(g: Game):
    sample = g.mouse_move(200, 0)
    assert sample, "no [KBM] mouse trace after injecting motion"
    assert sample["dx"] != 0 or sample["rx"] != 0, f"motion vanished: {sample}"


@test("a bigger mouse move deflects the stick further")
def mouse_scale(g: Game):
    small = g.mouse_move(20, 0)
    big = g.mouse_move(400, 0)
    assert small and big, f"missing traces: {small} {big}"
    assert abs(big["rx"]) > abs(small["rx"]), f"not scaled: small={small} big={big}"
