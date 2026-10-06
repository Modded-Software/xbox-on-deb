#!/usr/bin/env python3
"""Input tests: does an injected X11 key actually reach the game's pad logic?

Each test injects a key and reads back the runtime's [INPUT] diagnostic, which
is the synthesized Xbox state the title sees. Run via recomp/tests/run.py.
"""
from framework import Game, test, hold, START, BACK, DPAD_UP, DPAD_DOWN


@test("Return reaches the framebuffer window")
def return_reaches_window(g: Game):
    sample = hold(g, "Return")
    assert sample["window_has_RETURN"] == 1, f"window never saw Return: {sample}"
    after = g.wait_input()
    assert after["window_has_RETURN"] == 0, f"Return stuck down: {after}"


@test("Return becomes the Start button")
def return_is_start(g: Game):
    sample = hold(g, "Return")
    assert sample["buttons"] & START, f"Start bit not set: {sample}"


@test("Backspace becomes the Back button")
def backspace_is_back(g: Game):
    sample = hold(g, "BackSpace")
    assert sample["buttons"] & BACK, f"Back bit not set: {sample}"


@test("Space is the A button (analog pressure 255)")
def space_is_a(g: Game):
    sample = hold(g, "space")
    assert sample["window_has_SPACE"] == 1, f"window never saw Space: {sample}"
    assert sample["A"] == 255, f"A pressure not 255: {sample}"


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
    sample = hold(g, "Up")
    assert sample["buttons"] & DPAD_UP, f"d-pad up bit not set: {sample}"


@test("Arrow Down is d-pad down")
def down_is_dpad_down(g: Game):
    sample = hold(g, "Down")
    assert sample["buttons"] & DPAD_DOWN, f"d-pad down bit not set: {sample}"


@test("the game keeps advancing frames")
def game_is_alive(g: Game):
    assert g.wait_frame_advance(timeout=8.0), f"frame counter frozen at {g.frame()}"


@test("a framebuffer capture is produced")
def framebuffer_capture(g: Game):
    digest = g.capture_hash()
    assert digest, "F12 capture did not produce framebuffer.bmp"
