#!/usr/bin/env python3
"""A small stdlib-only test framework for the recompiled StarCraft: Ghost build.

The point is to make "did the feature actually run" checkable without a human
at the keyboard, and to have somewhere to keep adding those checks.

A `Game` owns one launched (or attached) process and gives tests four kinds of
feedback:

  * injection   -- focus()/key()/btn()/move(), via recomp/tests/xinject.py
  * input state -- wait_input(), the runtime's [INPUT] diagnostic (buttons,
                   sticks, what the framebuffer window saw)
  * liveness    -- title()/frame()/fps() from the window caption, so a frozen
                   game is distinguishable from an unresponsive one
  * pixels      -- capture_hash(), the F12 framebuffer dump, so a test can see
                   that the scene changed, not just that a key arrived

Tests are plain functions decorated with @test("..."). run_all() runs every
registered test against one Game and prints a PASS/FAIL summary.

Usage (from a test module):
    from framework import Game, test
    @test("Start reaches the game")
    def start(g):
        before = g.wait_input(hold(g, "Return"))
        assert before["buttons"] & 0x10
"""
import os
import re
import signal
import subprocess
import sys
import time
import hashlib

ROOT = "/home/agent/WORKSPACE-VM/projects/xbox-on-deb"
GAME_DIR = os.path.join(ROOT, "recomp", "game")
LOG = os.path.join(GAME_DIR, "recomp_boot.log")
XINJECT = os.path.join(ROOT, "recomp", "tests", "xinject.py")
CAPTURE = os.path.join(GAME_DIR, "framebuffer.bmp")
WINDOW_TITLE = "StarCraft"

# XInput button bits we assert on (see xinput_xbox.h).
START = 0x0010
BACK = 0x0020
DPAD_UP = 0x0001
DPAD_DOWN = 0x0002
DPAD_LEFT = 0x0004
DPAD_RIGHT = 0x0008


def _run(*args, check=True):
    result = subprocess.run([XINJECT, *args], capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"xinject {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def hold(game, name, wait=1.6):
    """Press a key and return the input sample taken while it is held."""
    game.key(name, "down")
    sample = game.wait_input()
    game.key(name, "up")
    return sample


class Game:
    def __init__(self, attach=False, kbm=True, boot_timeout=90):
        self.attach = attach
        self.kbm = kbm
        self.boot_timeout = boot_timeout
        self.proc = None
        self._log_pos = 0

    # -- lifecycle ---------------------------------------------------------

    def start(self):
        if self.attach:
            if not os.path.exists(LOG):
                raise RuntimeError(f"attach requested but {LOG} does not exist")
            self._log_pos = os.path.getsize(LOG)
            _run("wait", WINDOW_TITLE, str(self.boot_timeout))
        else:
            env = dict(os.environ)
            env["KBM"] = "1" if self.kbm else "0"
            env["DIAG"] = "1"
            env["RECOMP_KEY_TRACE"] = "1"
            env["RECOMP_FB_CAPTURE"] = CAPTURE
            try:
                os.remove(LOG)
            except FileNotFoundError:
                pass
            out = open(os.path.join("/tmp/opencode", "test_game.out"), "w")
            self.proc = subprocess.Popen(
                ["bash", "scripts/14-launch-recomp.sh"], cwd=ROOT, env=env,
                stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                start_new_session=True)
            _run("wait", WINDOW_TITLE, str(self.boot_timeout))
            self._log_pos = 0
        self.focus()
        return self

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()

    # -- injection ---------------------------------------------------------

    def focus(self):
        return _run("focus", WINDOW_TITLE)

    def key(self, name, action):
        return _run("key", name, action)

    def btn(self, number, action):
        return _run("btn", str(number), action)

    def move(self, dx, dy):
        return _run("move", str(dx), str(dy))

    # -- telemetry: input state -------------------------------------------

    def _read_from(self, offset):
        if not os.path.exists(LOG):
            return offset, ""
        with open(LOG, "r", errors="replace") as handle:
            handle.seek(offset)
            text = handle.read()
            return handle.tell(), text

    def latest_input(self):
        with open(LOG, "r", errors="replace") as handle:
            last = None
            for line in handle:
                if "[INPUT]" in line:
                    last = line
        if last is None:
            raise RuntimeError("no [INPUT] line in the boot log yet")
        return self._parse_input(last)

    def wait_input(self, timeout=6.0):
        """Wait for the next fresh [INPUT] sample and return it as a dict."""
        deadline = time.time() + timeout
        offset = os.path.getsize(LOG) if os.path.exists(LOG) else 0
        while time.time() < deadline:
            offset, text = self._read_from(offset)
            for line in text.splitlines():
                if "[INPUT]" in line:
                    return self._parse_input(line)
            time.sleep(0.1)
        raise TimeoutError("no new [INPUT] sample arrived")

    @staticmethod
    def _parse_input(line):
        sample = {}
        for key, value in re.findall(r"(\w+)=(\S+)", line):
            try:
                sample[key] = int(value, 0)
            except ValueError:
                sample[key] = value
        return sample

    def key_trace(self):
        """Recently arriving keys, from the window's own edge log."""
        with open(LOG, "r", errors="replace") as handle:
            return [l for l in handle if "[KEY]" in l]

    # -- telemetry: liveness / pixels -------------------------------------

    def title(self):
        return _run("title", WINDOW_TITLE)

    def frame(self):
        match = re.search(r"Frame (\d+)", self.title())
        return int(match.group(1)) if match else -1

    def fps(self):
        match = re.search(r"([\d.]+) FPS", self.title())
        return float(match.group(1)) if match else -1.0

    def wait_frame_advance(self, timeout=10.0):
        start = self.frame()
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.frame() > start:
                return True
            time.sleep(0.2)
        return False

    def capture_hash(self, timeout=5.0):
        """Trigger a framebuffer dump (F12) and hash it; None if it never came."""
        try:
            os.remove(CAPTURE)
        except FileNotFoundError:
            pass
        self.focus()
        self.key("F12", "press")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if os.path.exists(CAPTURE) and os.path.getsize(CAPTURE) > 0:
                time.sleep(0.1)  # let the write finish
                with open(CAPTURE, "rb") as handle:
                    return hashlib.sha256(handle.read()).hexdigest()[:16]
            time.sleep(0.1)
        return None


# -- test registry --------------------------------------------------------

_REGISTRY = []


def test(name=None):
    def decorate(fn):
        _REGISTRY.append((name or fn.__name__, fn))
        return fn
    return decorate


def registered():
    return list(_REGISTRY)


def run_all(game, only=None):
    passed, failed = 0, 0
    for name, fn in registered():
        if only and only not in name:
            continue
        game.focus()
        try:
            fn(game)
            print(f"  PASS  {name}")
            passed += 1
        except Exception as error:  # noqa: BLE001 - report anything a test raises
            print(f"  FAIL  {name}: {type(error).__name__}: {error}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    return failed == 0
