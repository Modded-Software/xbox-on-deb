#!/usr/bin/env python3
#!/usr/bin/env python3
"""Runner for the recompiled-game test suite.

    recomp/tests/run.py                 launch the game and run every test
    recomp/tests/run.py --attach        use a game that is already running
    recomp/tests/run.py --only dpad     run tests whose name contains "dpad"
    recomp/tests/run.py --scene         print the current scene fingerprint
    recomp/tests/run.py --record        append the current scene to baselines

Test modules are any test_*.py next to this file; importing them registers
their @test cases with the framework.
"""
import argparse
import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import framework  # noqa: E402
from framework import Game  # noqa: E402

BASELINES = os.path.join(HERE, "baselines", "scenes.txt")


def load_tests():
    for entry in sorted(os.listdir(HERE)):
        if entry.startswith("test_") and entry.endswith(".py"):
            importlib.import_module(entry[:-3])


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
    args = parser.parse_args()

    load_tests()
    game = Game(attach=args.attach, boot_timeout=args.boot_timeout)
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
    finally:
        game.stop()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
