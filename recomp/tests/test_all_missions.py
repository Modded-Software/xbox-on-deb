#!/usr/bin/env python3
"""Hidden-content regression: every mission selectable + The Borgo Refinery.

Two independent things have to be true for the cut level to be playable:

  1. the title is told to make every mission selectable (the launch script
     passes the guest command-line switch that sets guest 0x42338C, so
     cProfile::IsMissionUnlocked returns 1 for every entry), and
  2. The Borgo Refinery (`1_3_REFINERY` -> `1_3_1a_Hive_StationOuter`) is an
     *enabled* MISSION in the single-player chronicle (`Misc/ghostsp.nsc`) with
     its level files present.

`scripts/18-launch-user.sh` passes the switch by default, so run this with the
user launcher and a matching selector:

    uv run python recomp/tests/run.py --user-state --only all-missions

Whether the level then *renders* is the user's call (see AGENTS.md).
"""
import os
import re

try:
    from . import tconfig
    from .framework import Game, test
except ImportError:
    import tconfig
    from framework import Game, test

BORGO_LEVEL = "1_3_1a_Hive_StationOuter"
BORGO_MISSION = "1_3_REFINERY"

HERE = os.path.dirname(os.path.abspath(__file__))
LAUNCHER = os.path.normpath(
    os.path.join(HERE, os.pardir, os.pardir, "scripts", "18-launch-user.sh"))

# The launcher owns the guest switch string; read it back from there so this
# test carries no second copy of the title's command-line token.
_LAUNCHER_CMDLINE = re.compile(r'RECOMP_CMDLINE="\$\{RECOMP_CMDLINE-([^}"]*)\}"')


def _guest_all_missions_switch():
    with open(LAUNCHER, "r", errors="replace") as handle:
        for line in handle:
            match = _LAUNCHER_CMDLINE.search(line)
            if match:
                return match.group(1)
    raise AssertionError(f"no RECOMP_CMDLINE default in {LAUNCHER}")


@test("all-missions: user launch passes the guest switch")
def user_launch_passes_all_missions(g: Game):
    # The runtime echoes the LaunchDataPage command line at boot
    # (refs/xboxrecomp/src/kernel/kernel_bridge.c). tconfig.LOG is repointed to
    # the live user-state log; mixins_telemetry's bound LOG is not, so read the
    # repointed path directly.
    switch = _guest_all_missions_switch()
    log = tconfig.LOG
    assert os.path.exists(log), f"no runtime log at {log}"
    with open(log, "r", errors="replace") as handle:
        for line in handle:
            if "command line" in line and switch in line:
                return
    raise AssertionError(
        f"no 'command line {switch}' in {log}: the user path did not pass the "
        "guest all-missions switch (is ALL_MISSIONS=0 set?)")


@test("all-missions: chronicle enables The Borgo Refinery")
def chronicle_enables_borgo(g: Game):
    nsc = os.path.join(tconfig.GAME_DIR, "game", "Misc", "ghostsp.nsc")
    assert os.path.exists(nsc), f"no chronicle at {nsc}"
    enabled = []
    with open(nsc, "r", errors="replace") as handle:
        for line in handle:
            stripped = line.lstrip()
            if stripped.startswith("//") or not stripped.startswith("MISSION"):
                continue
            if BORGO_LEVEL in line:
                enabled.append(line.strip())
    assert enabled, f"no enabled MISSION ... {BORGO_LEVEL} in {nsc}"
    assert BORGO_MISSION in enabled[0], enabled[0]


@test("all-missions: The Borgo Refinery level files are present")
def borgo_level_files_present(g: Game):
    # The engine loads the .nhc out of the .nil container, so only the on-disk
    # package files are checked here (the same three every level ships).
    levels = os.path.join(tconfig.GAME_DIR, "game", "Levels")
    missing = [ext for ext in (".nil", ".npd", ".nsd")
               if not os.path.exists(os.path.join(levels, BORGO_LEVEL + ext))]
    assert not missing, f"missing Borgo level files {missing} under {levels}"