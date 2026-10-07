#!/usr/bin/env python3
"""Integration test: ghost.exe plays mission audio all the way to the end.

The test records ghost.exe's own PipeWire output stream (the signal the sound
server really gets). It starts as soon as the mission map streams in, drives
through the briefing into interactive gameplay, and requires audio *through the
end* of the window -- a briefing FMV blip at the start is not enough.

Run it with:

    recomp/tests/run.py --user-state --only audible
"""
import array
import math
import os
import time
import wave

from framework import Game, test

ENTER_SECONDS = 20.0    # briefing / loading screens: keep pressing A to advance
PLAY_SECONDS = 10.0     # interactive gameplay
WINDOW_SECONDS = 2.0
FINAL_PEAK = 1000
FINAL_RMS = 30.0


def _windows(path, window_seconds):
    """[(rms, peak), ...] for consecutive `window_seconds` slices of `path`."""
    with wave.open(path, "rb") as handle:
        rate = handle.getframerate()
        channels = handle.getnchannels()
        frames = handle.readframes(handle.getnframes())
    samples = array.array("h")
    samples.frombytes(frames[:len(frames) // 2 * 2])
    per = max(1, int(window_seconds * rate * channels))
    out = []
    for start in range(0, len(samples), per):
        chunk = samples[start:start + per]
        if not chunk:
            break
        rms = math.sqrt(sum(float(s) * s for s in chunk) / len(chunk))
        out.append((rms, max(abs(s) for s in chunk)))
    return out


@test("the mission is audible", timeout=360)
def mission_is_audible(g: Game):
    assert g.goto_mission(key="space", gap=2.0, timeout=240.0) == g.MISSION_MAP, \
        "could not reach the first mission"

    host = "/tmp/opencode/mission_host.wav"
    try:
        os.remove(host)
    except FileNotFoundError:
        pass
    # The map name in the log means the scene is streaming in; capture from
    # there so the whole approach into gameplay is covered.
    rec = g.start_app_recording(host)

    # The level streams, then the shuttle-escape cutscene and the briefing FMV
    # play before the player gains control. Keep pressing A to advance through
    # them; audio (including the briefing) should be present the whole time.
    deadline = time.time() + ENTER_SECONDS
    while time.time() < deadline:
        g.tap("space", hold=0.3, gap=0.5)

    # Interactive gameplay: move, turn, jump, fire. Audio must keep playing
    # right up to the end of the window.
    deadline = time.time() + PLAY_SECONDS
    while time.time() < deadline:
        g.move(80, 0, count=8, interval_ms=20)
        g.tap("w", hold=0.25, gap=0.01)
        g.tap("space", hold=0.2, gap=0.01)
        g.tap("b", hold=0.2, gap=0.01)
    rec.stop()

    assert os.path.exists(host) and os.path.getsize(host) > 44, \
        f"no host audio was recorded at {host}"
    windows = _windows(host, WINDOW_SECONDS)
    loud = [(r, p) for r, p in windows if p > FINAL_PEAK and r > FINAL_RMS]
    first = windows[0]
    last = windows[-1]
    assert last[1] > FINAL_PEAK and last[0] > FINAL_RMS, (
        f"ghost.exe's host audio stream is silent at the END of mission "
        f"gameplay: last rms={last[0]:.1f} peak={last[1]}, "
        f"{len(loud)}/{len(windows)} audible windows; "
        f"first rms={first[0]:.1f} peak={first[1]}")