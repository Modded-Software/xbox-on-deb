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


def _ghost_pids():
    """PIDs of any running ghost.exe, found via /proc (Proton detaches it
    from the launched session, so killing the process group is not enough).

    Match the binary path, not the bare name: a shell command that merely
    mentions "ghost.exe" (say, the one running these tests) must not be
    mistaken for the game."""
    me = os.getpid()
    pids = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit() or int(entry) == me:
            continue
        try:
            with open(f"/proc/{entry}/cmdline", "rb") as handle:
                cmdline = handle.read().replace(b"\x00", b" ").decode("utf-8", "replace")
        except OSError:
            continue
        if "/ghost.exe" in cmdline or "\\ghost.exe" in cmdline:
            pids.append(int(entry))
    return pids


def kill_ghost():
    """Terminate every running ghost.exe, then force-kill any survivor."""
    pids = _ghost_pids()
    if not pids:
        return 0
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.time() + 10
    while time.time() < deadline and _ghost_pids():
        time.sleep(0.2)
    for pid in _ghost_pids():
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    return len(pids)


def hold(game, name, wait=4.0, expect=None):
    """Press a key and return an input sample taken while it is held.

    `expect` maps sample fields to a required value (a bitmask is ANDed). The
    key stays down until a fresh [INPUT] sample satisfies it, because that
    diagnostic is emitted only once a second and may be delayed by a busy
    frame; releasing early would sample the released state."""
    deadline = time.time() + wait
    game.key(name, "down")
    sample = None
    try:
        while time.time() < deadline:
            try:
                sample = game.wait_input(timeout=min(1.5, deadline - time.time()))
            except TimeoutError:
                continue
            if expect is None or all(sample.get(k, 0) & v for k, v in expect.items()):
                break
    finally:
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
            kill_ghost()  # clear any stale instance so runs never stack
            env = dict(os.environ)
            env["KBM"] = "1" if self.kbm else "0"
            env["DIAG"] = "1"
            env["RECOMP_KEY_TRACE"] = "1"
            env["RECOMP_KBM_TRACE"] = "1"
            env["RECOMP_FB_CAPTURE"] = CAPTURE
            try:
                os.remove(LOG)
            except FileNotFoundError:
                pass
            out = open(os.path.join("/tmp/opencode", "test_game.out"), "w")
            try:
                self.proc = subprocess.Popen(
                    ["bash", "scripts/14-launch-recomp.sh"], cwd=ROOT, env=env,
                    stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                    start_new_session=True)
            finally:
                out.close()  # the child holds its own copy
            _run("wait", WINDOW_TITLE, str(self.boot_timeout))
            self._log_pos = 0
        self.focus()
        return self

    def stop(self):
        if self.attach:
            return
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
        self.proc = None
        kill_ghost()

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

    def move(self, dx, dy, count=1, interval_ms=0):
        """Sustained motion: repeat the relative move `count` times."""
        args = ["move", str(dx), str(dy)]
        if count != 1 or interval_ms:
            args += [str(count), str(interval_ms)]
        return _run(*args)

    def tap(self, name, hold=0.35, gap=0.5):
        """A press long enough to span an input poll, then let the UI settle."""
        self.key(name, "down")
        time.sleep(hold)
        self.key(name, "up")
        time.sleep(gap)

    def start_new_game(self, taps=5, gap=1.5):
        """Advance the menus into a mission by tapping A (Return), as a human
        would. Returns the frame counter when the taps finish."""
        for _ in range(taps):
            self.tap("Return", gap=gap)
        return self.frame()

    # -- telemetry: mouse / right stick -----------------------------------

    def mouse_move(self, dx, dy, timeout=4.0):
        """Inject relative mouse motion and wait for the input layer to report
        the synthesised right-stick value. None if nothing arrived."""
        offset = os.path.getsize(LOG) if os.path.exists(LOG) else 0
        self.move(dx, dy)
        deadline = time.time() + timeout
        while time.time() < deadline:
            offset, text = self._read_from(offset)
            for line in text.splitlines():
                found = re.search(
                    r"\[KBM\] mouse dx=(-?\d+) dy=(-?\d+) rx=(-?\d+) ry=(-?\d+)", line)
                if found:
                    return dict(zip(("dx", "dy", "rx", "ry"),
                                    (int(v) for v in found.groups())))
            time.sleep(0.05)
        return None

    def mouse_trace(self):
        with open(LOG, "r", errors="replace") as handle:
            return [l for l in handle if "[KBM] mouse" in l]

    def log_offset(self):
        return os.path.getsize(LOG) if os.path.exists(LOG) else 0

    def log_since(self, offset, tag):
        """Lines containing `tag` appended to the boot log since `offset`."""
        _, text = self._read_from(offset)
        return [l for l in text.splitlines() if tag in l]

    def wait_log_line(self, tag, timeout=25.0, offset=None):
        """Wait for the next boot-log line containing `tag`; None on timeout."""
        if offset is None:
            offset = self.log_offset()
        deadline = time.time() + timeout
        while time.time() < deadline:
            lines = self.log_since(offset, tag)
            if lines:
                return lines[-1]
            time.sleep(0.5)
        return None

    # -- telemetry: GPU health --------------------------------------------

    def shader_failures(self):
        """Vertex+pixel D3DCompile failures from the latest GPU summary."""
        line = self._last_line("[GPU-D3D11] shaders:")
        if line is None:
            return None
        return sum(int(n) for n in re.findall(r"(\d+) failures", line))

    def texture_failures(self):
        """Texture decode+create failures from the latest GPU summary."""
        line = self._last_line("[GPU-D3D11] texture uploads:")
        if line is None:
            return None
        return sum(int(n) for n in re.findall(r"(\d+) (?:decode|create) failures", line))

    def cpu_fallback_batches(self):
        line = self._last_line("[GPU-D3D11] batches:")
        if line is None:
            return None
        match = re.search(r"(\d+) CPU fallback", line)
        return int(match.group(1)) if match else None

    def _last_line(self, tag):
        if not os.path.exists(LOG):
            return None
        last = None
        with open(LOG, "r", errors="replace") as handle:
            for line in handle:
                if tag in line:
                    last = line
        return last

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


def _test_alarm(_signum, _frame):
    raise TimeoutError("test exceeded its time limit (game may have hung)")


def run_all(game, only=None, per_test_timeout=90):
    passed, failed = 0, 0
    previous = signal.signal(signal.SIGALRM, _test_alarm)
    for name, fn in registered():
        if only and only not in name:
            continue
        signal.alarm(per_test_timeout)
        try:
            game.focus()
            fn(game)
            print(f"  PASS  {name}")
            passed += 1
        except Exception as error:  # noqa: BLE001 - report anything a test raises
            print(f"  FAIL  {name}: {type(error).__name__}: {error}")
            failed += 1
        finally:
            signal.alarm(0)
    signal.signal(signal.SIGALRM, previous)
    print(f"\n{passed} passed, {failed} failed")
    return failed == 0
