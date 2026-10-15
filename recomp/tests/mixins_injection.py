"""Input injection and scripted controller taps for the recomp test suite."""
import os
import time

try:
    from .procutil import _run
    from .tconfig import WINDOW_TITLE, log
except ImportError:
    from procutil import _run
    from tconfig import WINDOW_TITLE, log


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
            except TimeoutError as exc:
                log.debug("wait_input timed out while holding %s: %s", name, exc)
                continue
            if expect is None or all(sample.get(k, 0) & v for k, v in expect.items()):
                break
    finally:
        game.key(name, "up")
    return sample


class InjectionMixin:
    def minimize(self):
        """Iconify the game window so the user's own keys cannot reach it.

        Injection is off-focus (the runtime's control file), so no test needs
        the window raised: iconifying keeps the user's typing out of the game
        and out of the run. Set RECOMP_LEGACY_FOCUS=1 to switch to the
        XTest/focus path, which does need the window up. RECOMP_TEST_VISIBLE=1
        leaves the window as it is (visible), for measuring what a player sees."""
        if os.environ.get("RECOMP_TEST_VISIBLE"):
            return None
        if os.environ.get("RECOMP_LEGACY_FOCUS"):
            return _run("focus", WINDOW_TITLE)
        return _run("minimize", WINDOW_TITLE, check=False)

    def focus(self):
        """Kept for callers; now iconifies the window (see minimize())."""
        return self.minimize()

    def key(self, name, action):
        # Keys go through the runtime's control file: no X input focus needed,
        # so taps do not steal the user's window.
        return _run("keyfile", name, action)

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
        """Advance the menus into a mission by tapping A, as a human would.

        A is Space in the default KBM layout (src/input/xinput_device.c), not
        Return -- Return is unmapped, so tapping it does nothing. Returns the
        frame counter when the taps finish."""
        for _ in range(taps):
            self.tap("space", gap=gap)
        return self.frame()