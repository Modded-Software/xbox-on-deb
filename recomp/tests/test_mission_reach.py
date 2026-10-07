#!/usr/bin/env python3
"""Integration test: reach the first mission by injecting the A-mash script.

Launches the *default user configuration* (scripts/18-launch-user.sh -- the same
entry point a human uses) and then drives it exactly as scripted: press A
(Space in the default KBM layout) every two seconds until the first mission's
map loads.

Run it with:

    recomp/tests/run.py --user-state --only a-mash

--user-state selects the user launcher and its runtime log; other test modules
assume the test env, so pair this with a selector that matches only this case.
From the shell directly:

    python3 recomp/tests/run.py --user-state --only a-mash
"""
from framework import Game, test


@test("a-mash reaches the first mission")
def a_mash_reaches_mission(g: Game):
    name = g.goto_mission(key="space", gap=2.0, timeout=240.0)
    assert name == g.MISSION_MAP, f"never reached the first mission (got {name})"
    assert g.wait_frame_advance(timeout=10.0), \
        "mission map loaded but the game is not rendering"