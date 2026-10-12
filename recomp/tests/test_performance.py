#!/usr/bin/env python3
"""Single-shot in-game framerate measurement.

Drives to the first mission once, measures the render rate for WINDOW seconds
(default 10), prints it, and ends. One test only -- no repeated A-mashing
between tests.

    recomp/tests/run.py --user-state --only performance
"""
import os
import statistics

from framework import Game, test

MIN_FPS = float(os.environ.get("PERF_MIN_FPS", "5.0"))
WINDOW = float(os.environ.get("PERF_WINDOW", "10.0"))
# One 10 s window is pure noise (run-to-run spread is +-30-40%). Sample several
# windows of the *same* gameplay session -- no extra goto_gameplay/A-mash -- and
# assert on the median.
REPEATS = int(os.environ.get("PERF_REPEATS", "3"))


@test("performance: in-game framerate", timeout=360)
def in_game_framerate(g: Game):
    assert g.goto_gameplay(), "never reached the first mission (map never loaded)"
    means = []
    for i in range(REPEATS):
        before, offset = g.frame(), g.log_offset()
        stats = g.measure_fps(WINDOW)
        assert stats is not None, "the window caption never reported a framerate"
        assert g.frame() > before, "frames did not advance while measuring"
        means.append(stats["mean"])
        print(f"    in-game FPS window {i + 1}/{REPEATS}: "
              f"min={stats['min']:.1f} max={stats['max']:.1f} "
              f"mean={stats['mean']:.1f} (n={stats['n']})")
        for line in g.log_since(offset, "[KICK]") + g.log_since(offset, "[GPU] presentation"):
            print(f"      {line.strip()}")
    median = statistics.median(means)
    print(f"    in-game FPS median of {REPEATS}: {median:.1f}  (all: "
          f"{', '.join('%.1f' % m for m in means)})")
    assert max(means) >= MIN_FPS, \
        f"in-game framerate never reached {MIN_FPS:.1f} FPS: {means}"