"""Stdlib-only test framework for the recompiled StarCraft: Ghost build.

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

The implementation is split across mixin modules (lifecycle, injection,
navigation, telemetry) plus tconfig/procutil/audio/registry; this module is the
public facade.

Usage (from a test module):
    from framework import Game, test
    @test("Start reaches the game")
    def start(g):
        before = g.wait_input(hold(g, "Return"))
        assert before["buttons"] & 0x10
"""
try:
    from .mixins_injection import InjectionMixin, hold
    from .mixins_lifecycle import LifecycleMixin
    from .mixins_nav import NavMixin
    from .mixins_telemetry import TelemetryMixin
    from .procutil import _ghost_pids, _run, kill_ghost
    from .registry import registered, run_all, test
    from .tconfig import (BACK, CAPTURE, DPAD_DOWN, DPAD_LEFT, DPAD_RIGHT,
                          DPAD_UP, GAME_DIR, INPUT_FILE, INPUT_HOST, LOG, ROOT,
                          START, WINDOW_TITLE, XINJECT, log)
except ImportError:
    from mixins_injection import InjectionMixin, hold
    from mixins_lifecycle import LifecycleMixin
    from mixins_nav import NavMixin
    from mixins_telemetry import TelemetryMixin
    from procutil import _ghost_pids, _run, kill_ghost
    from registry import registered, run_all, test
    from tconfig import (BACK, CAPTURE, DPAD_DOWN, DPAD_LEFT, DPAD_RIGHT,
                         DPAD_UP, GAME_DIR, INPUT_FILE, INPUT_HOST, LOG, ROOT,
                         START, WINDOW_TITLE, XINJECT, log)


class Game(LifecycleMixin, InjectionMixin, NavMixin, TelemetryMixin):
    def __init__(self, attach=False, kbm=True, boot_timeout=90, user_state=False):
        self.attach = attach
        self.kbm = kbm
        self.boot_timeout = boot_timeout
        self.user_state = user_state
        self.proc = None
        self._log_pos = 0


__all__ = [
    "Game", "test", "hold", "registered", "run_all", "kill_ghost",
    "log", "START", "BACK", "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT",
    "DPAD_RIGHT", "CAPTURE", "GAME_DIR", "LOG", "ROOT", "INPUT_HOST",
    "INPUT_FILE", "WINDOW_TITLE", "XINJECT",
]