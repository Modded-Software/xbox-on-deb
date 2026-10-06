#!/usr/bin/env python3
"""Input tests: does an injected X11 key actually reach the game's pad logic?

Each test injects a key and reads back the runtime's [INPUT] diagnostic, which
is the synthesized Xbox state the title sees. Run via recomp/tests/run.py.

These exercise the modern desktop layout (see src/input/xinput_device.c):
  Return = A (confirm/action)   E = B (use)        space = X (jump)
  R = Y   Q = White   F = Black  Tab = Start   BackSpace/Escape = Back
  WASD = left stick   mouse = right stick   LMB = RT   RMB = LT
"""
from framework import Game, test, hold, START, BACK, DPAD_UP, DPAD_DOWN


@test("the game keeps advancing frames")
def game_is_alive(g: Game):
    assert g.wait_frame_advance(timeout=8.0), f"frame counter frozen at {g.frame()}"


@test("Return reaches the framebuffer window")
def return_reaches_window(g: Game):
    sample = hold(g, "Return")
    assert sample["window_has_RETURN"] == 1, f"window never saw Return: {sample}"
    after = g.wait_input()
    assert after["window_has_RETURN"] == 0, f"Return stuck down: {after}"


@test("Return is the A button (analog pressure 255)")
def return_is_a(g: Game):
    sample = hold(g, "Return", expect={"A": 255})
    assert sample["A"] == 255, f"A pressure not 255: {sample}"


@test("E is the B button (use/interact)")
def e_is_b(g: Game):
    sample = hold(g, "e", expect={"B": 255})
    assert sample["B"] == 255, f"B pressure not 255: {sample}"


@test("space is the X button (jump)")
def space_is_x(g: Game):
    sample = hold(g, "space", expect={"X": 255})
    assert sample["window_has_SPACE"] == 1, f"window never saw space: {sample}"
    assert sample["X"] == 255, f"X pressure not 255: {sample}"


@test("Tab is the Start button")
def tab_is_start(g: Game):
    sample = hold(g, "Tab", expect={"buttons": START})
    assert sample["buttons"] & START, f"Start bit not set: {sample}"


@test("Backspace is the Back button")
def backspace_is_back(g: Game):
    sample = hold(g, "BackSpace", expect={"buttons": BACK})
    assert sample["buttons"] & BACK, f"Back bit not set: {sample}"


@test("W drives the left stick up")
def w_left_stick(g: Game):
    sample = hold(g, "w")
    assert sample["LY"] > 0, f"LY not positive for W: {sample}"


@test("D drives the left stick right")
def d_left_stick(g: Game):
    sample = hold(g, "d")
    assert sample["LX"] > 0, f"LX not positive for D: {sample}"


@test("Arrow Up is d-pad up")
def up_is_dpad_up(g: Game):
    sample = hold(g, "Up", expect={"buttons": DPAD_UP})
    assert sample["buttons"] & DPAD_UP, f"d-pad up bit not set: {sample}"


@test("Arrow Down is d-pad down")
def down_is_dpad_down(g: Game):
    sample = hold(g, "Down", expect={"buttons": DPAD_DOWN})
    assert sample["buttons"] & DPAD_DOWN, f"d-pad down bit not set: {sample}"


@test("a framebuffer capture is produced")
def framebuffer_capture(g: Game):
    digest = g.capture_hash()
    assert digest, "F12 capture did not produce framebuffer.bmp"
