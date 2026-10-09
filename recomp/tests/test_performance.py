#!/usr/bin/env python3
"""Single-shot in-game framerate measurement.

Drives to the first mission once, measures the render rate for WINDOW seconds
(default 10), prints it, and ends. One test only -- no repeated A-mashing
between tests.

    recomp/tests/run.py --user-state --only performance
"""
import os

from framework import Game, test

MIN_FPS = float(os.environ.get("PERF_MIN_FPS", "5.0"))
WINDOW = float(os.environ.get("PERF_WINDOW", "10.0"))


@test("performance: in-game framerate", timeout=360)
def in_game_framerate(g: Game):
    assert g.goto_gameplay(), "never reached the first mission (map never loaded)"
    before, offset = g.frame(), g.log_offset()
    stats = g.measure_fps(WINDOW)
    assert stats is not None, "the window caption never reported a framerate"
    assert g.frame() > before, "frames did not advance while measuring"
    print(f"    in-game FPS: min={stats['min']:.1f} max={stats['max']:.1f} "
          f"mean={stats['mean']:.1f} (n={stats['n']})")
    for line in g.log_since(offset, "[KICK]") + g.log_since(offset, "[GPU] presentation"):
        print(f"    {line.strip()}")
    assert stats["max"] >= MIN_FPS, \
        f"in-game framerate never reached {MIN_FPS:.1f} FPS: {stats}"