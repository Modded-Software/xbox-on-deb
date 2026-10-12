"""Paths, environment variables and constants for the recomp test suite.

Split out of framework.py so no single test module exceeds the CI source-file
limit. Imported as ``tconfig`` when running from recomp/tests, or as
``recomp.tests.tconfig`` when imported as a package.
"""
import logging
import os

log = logging.getLogger("recomp.tests.framework")

# The repo root is derived from this file (recomp/tests/tconfig.py -> repo
# root); RECOMP_ROOT overrides it for a relocated checkout.
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("RECOMP_ROOT") or os.path.dirname(os.path.dirname(_HERE))

# RECOMP_GAME_DIR selects a parallel game tree (e.g. recomp/game-backup, built
# against refs/xboxrecomp.backup) so a second runtime can be A/B'd.
GAME_DIR = os.environ.get("RECOMP_GAME_DIR", os.path.join(ROOT, "recomp", "game"))
LOG = os.path.join(GAME_DIR, "recomp_boot.log")
XINJECT = os.path.join(ROOT, "recomp", "tests", "xinject.py")
CAPTURE = os.path.join(GAME_DIR, "framebuffer.bmp")
WINDOW_TITLE = "StarCraft"

# Off-focus key injection: the runtime polls this control file
# (src/video/fb_present.c:fb_inject_poll) instead of taking X input focus, so
# an automated run never pulls focus from the user. RECOMP_INPUT_HOST is the
# host path xinject writes; RECOMP_INPUT_FILE is how the runtime opens it.
INPUT_HOST = os.path.expanduser(
    os.environ.get("RECOMP_INPUT_HOST",
                   "~/Games/scghost-prefix/pfx/drive_c/recomp-input.txt"))
INPUT_FILE = os.environ.get("RECOMP_INPUT_FILE", r"C:\recomp-input.txt")
os.environ["RECOMP_INPUT_HOST"] = INPUT_HOST

# XInput button bits we assert on (see xinput_xbox.h).
START = 0x0010
BACK = 0x0020
DPAD_UP = 0x0001
DPAD_DOWN = 0x0002
DPAD_LEFT = 0x0004
DPAD_RIGHT = 0x0008