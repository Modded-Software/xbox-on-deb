#!/usr/bin/env python3
"""Runner for the recompiled-game test suite.

    uv run python recomp/tests/run.py                 launch the game and run every test
    uv run python recomp/tests/run.py --attach        use a game that is already running
    uv run python recomp/tests/run.py --only dpad     run tests whose name contains "dpad"
    uv run python recomp/tests/run.py --scene         print the current scene fingerprint
    uv run python recomp/tests/run.py --record        append the current scene to baselines

Test modules are the test_*.py files next to this one; importing them registers
their @test cases with the framework. They are imported explicitly below, so the
runner needs no dynamic import: add a line when you add a test module.
"""
import argparse
import os
import signal
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import framework
import tconfig
from framework import Game

# Explicit test-module imports, alphabetical so the run order is stable
# (test_zzz_gameplay last). Each import registers its @test cases.
import test_all_missions
import test_audio_monitor
import test_cloak_effect
import test_input
import test_mission_audio
import test_mission_reach
import test_mouse
import test_performance
import test_replay_audio
import test_zzz_gameplay

BASELINES = os.path.join(HERE, "baselines", "scenes.txt")


def _on_signal(signum, _frame):
    """Ctrl-C or a kill must not leave the game running."""
    framework.kill_ghost()
    sys.exit(128 + signum)


signal.signal(signal.SIGINT, _on_signal)
signal.signal(signal.SIGTERM, _on_signal)


def _log_size():
    try:
        return os.path.getsize(tconfig.LOG)
    except OSError as exc:
        print(f"[HOLD] cannot stat {tconfig.LOG}: {exc}")
        return -1


def _hold(secs):
    """Keep the game in whatever state the tests left it for `secs`, and
    report how much the runtime log grew meanwhile (machine-readable lines)."""
    before = _log_size()
    t0 = time.monotonic()
    print(f"[HOLD] start log_bytes={before} log={tconfig.LOG}", flush=True)
    time.sleep(secs)
    after = _log_size()
    dt = time.monotonic() - t0
    print(f"[HOLD] end log_bytes={after} secs={dt:.1f} "
          f"rate_Bps={(after - before) / dt:.0f}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attach", action="store_true",
                        help="use an already-running game instead of launching")
    parser.add_argument("--only", default=None, help="substring of test names to run")
    parser.add_argument("--scene", action="store_true",
                        help="print + optionally record the current scene fingerprint")
    parser.add_argument("--record", action="store_true",
                        help="with --scene, append the fingerprint to baselines/scenes.txt")
    parser.add_argument("--boot-timeout", type=float, default=90.0)
    parser.add_argument("--user-state", action="store_true",
                        help="launch the default user configuration "
                             "(scripts/18-launch-user.sh) instead of the test env")
    parser.add_argument("--hold", type=float, default=0.0,
                        help="keep the game running SECS after the tests, "
                             "printing the runtime log size before and after "
                             "(steady-state log rate; scripts/27-measure-logging.sh)")
    args = parser.parse_args()

    game = Game(attach=args.attach, boot_timeout=args.boot_timeout,
                user_state=args.user_state)
    ok = False
    try:
        game.start()
        if args.scene:
            digest = game.capture_hash()
            line = f"{digest} frame={game.frame()} fps={game.fps():.1f} title={game.title()}"
            print(line)
            if args.record and digest:
                os.makedirs(os.path.dirname(BASELINES), exist_ok=True)
                with open(BASELINES, "a") as handle:
                    handle.write(line + "\n")
            return 0
        ok = framework.run_all(game, only=args.only)
        if args.hold > 0:
            _hold(args.hold)
    finally:
        game.stop()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())