#!/usr/bin/env python3
"""Gameplay tests: can we get from the menu into a mission and interact?

This module sorts last (test_zzz_*) because it drives the game into a mission
and leaves it there, unlike the input tests which are happy in the menu.
"""
import time

from framework import Game, test


def _ensure_mission(g: Game):
    if getattr(g, "_in_mission", False):
        return
    g.start_new_game(taps=5, gap=1.5)
    g._in_mission = True


@test("five A presses leave the menu")
def five_a_presses(g: Game):
    menu = g.capture_hash()
    g.start_new_game(taps=5, gap=1.5)
    time.sleep(2.0)
    scene = g.capture_hash()
    assert scene and scene != menu, f"still in the menu ({menu} -> {scene})"
    g._in_mission = True


@test("a mission renders at a usable framerate")
def mission_fps(g: Game):
    _ensure_mission(g)
    best = 0.0
    deadline = time.time() + 6.0
    while time.time() < deadline:
        best = max(best, g.fps())
        time.sleep(0.5)
    assert best > 5.0, f"mission never exceeded {best:.1f} FPS"


@test("the mouse turns the camera in a mission")
def mouse_camera(g: Game):
    _ensure_mission(g)
    before = g.capture_hash()
    g.move(60, 0, count=25, interval_ms=30)
    time.sleep(0.8)
    after = g.capture_hash()
    assert before and after, f"capture failed ({before} -> {after})"
    assert after != before, "camera did not move when the mouse did"


@test("mouse right steers the stick right in a mission")
def mouse_direction(g: Game):
    _ensure_mission(g)
    right = g.mouse_move(200, 0)
    assert right and right["rx"] > 0, f"rightward motion not right: {right}"
    left = g.mouse_move(-200, 0)
    assert left and left["rx"] < 0, f"leftward motion not left: {left}"


@test("the stick is silent when the mouse is still")
def mouse_no_drift(g: Game):
    _ensure_mission(g)
    g.mouse_move(200, 0)
    time.sleep(1.0)
    offset = g.log_offset()
    time.sleep(1.5)
    fresh = g.log_since(offset, "[KBM] mouse")
    assert not fresh, f"mouse kept reporting motion while still: {fresh[:3]}"


@test("every shader compiles during play")
def shaders_compile(g: Game):
    _ensure_mission(g)
    line = g.wait_log_line("[GPU-D3D11] shaders:", timeout=30)
    assert line, "no GPU shader summary appeared"
    assert g.shader_failures() == 0, f"shader compile failures: {line.strip()}"


@test("every texture decodes during play")
def textures_decode(g: Game):
    _ensure_mission(g)
    line = g.wait_log_line("[GPU-D3D11] texture uploads:", timeout=30)
    assert line, "no GPU texture summary appeared"
    assert g.texture_failures() == 0, f"texture failures: {line.strip()}"


@test("no draw falls back to the CPU")
def no_cpu_fallback(g: Game):
    _ensure_mission(g)
    line = g.wait_log_line("[GPU-D3D11] batches:", timeout=30)
    assert line, "no GPU batch summary appeared"
    assert g.cpu_fallback_batches() == 0, f"CPU fallback: {line.strip()}"
