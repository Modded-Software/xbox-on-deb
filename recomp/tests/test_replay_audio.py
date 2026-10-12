#!/usr/bin/env python3
"""Integration test: replay a recorded session, minimized, and require that the
emulated APU never goes silent for good.

The 5th-pass freeze fix once killed all sound ~47 s into ghost-collision-5 (the
timer thread wedged, so DirectSound's DPCs stopped). Nothing in the log shows
it; only the APU's own PCM does. This replays the session hands-free and scans
RECOMP_APU_WAV's <path>.emu.raw (16-bit LE stereo @ 48 kHz) per second.

    REPLAY=1 SESSION=ghost-collision-5 recomp/tests/run.py --user-state --only replay-audio
    make test-replay-audio SESSION=ghost-collision-5

Standalone, on an existing capture:  test_replay_audio.py <file.emu.raw>
"""
import array
import math
import os
import sys
import time

from framework import Game, test

RATE, CHANNELS = 48000, 2
SECONDS = float(os.environ.get("RECOMP_REPLAY_SECONDS", "160"))
SILENT_RMS = 20.0     # the wedged capture sat at rms ~6.5
LOUD_RMS = 100.0
MAX_SILENT_RUN = 10   # seconds of continuous silence after sound started


def per_second_rms(path):
    data = open(path, "rb").read()
    s = array.array("h")
    s.frombytes(data[:len(data) // 2 * 2])
    per = RATE * CHANNELS
    return [math.sqrt(sum(float(v) * v for v in s[i:i + per]) / len(s[i:i + per]))
            for i in range(0, len(s) - per + 1, per)]


def longest_silence_after_sound(rms):
    """(start second, length) of the longest silent run after the first loud second."""
    best, run, start = (0, 0), 0, 0
    try:
        first = next(i for i, r in enumerate(rms) if r > LOUD_RMS)
    except StopIteration:
        return (0, len(rms))
    for i in range(first, len(rms)):
        if rms[i] < SILENT_RMS:
            if run == 0:
                start = i
            run += 1
            if run > best[1]:
                best = (start, run)
        else:
            run = 0
    return best


def report(rms):
    bar = "".join("." if r < SILENT_RMS else ("o" if r > LOUD_RMS else "-") for r in rms)
    start, length = longest_silence_after_sound(rms)
    print(f"[replay-audio] {len(rms)} s, longest silence after sound: {length} s at {start} s",
          file=sys.stderr, flush=True)
    print(f"[replay-audio] level: {bar}", file=sys.stderr, flush=True)
    return length


@test("replay-audio: APU stays alive through a replayed session", timeout=int(SECONDS) + 240)
def replay_audio(g: Game):
    assert os.environ.get("REPLAY") == "1" and os.environ.get("SESSION"), \
        "launch with REPLAY=1 SESSION=<id> (see module docstring)"
    time.sleep(SECONDS)
    raw = g.audio_raw + ".emu.raw"
    assert os.path.exists(raw), f"no APU capture at {raw}"
    length = report(per_second_rms(raw))
    assert length < MAX_SILENT_RUN, f"APU silent for {length} s after sound started (wedge)"


def _self_check():
    loud, quiet = [500.0] * 5, [5.0] * 12
    assert longest_silence_after_sound([5.0] * 3 + loud + [5.0] * 4 + loud) == (8, 4)
    assert longest_silence_after_sound(loud + quiet) == (5, 12)
    assert longest_silence_after_sound(quiet) == (0, 12)
    print("self-check ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-check"]:
        _self_check()
    else:
        sys.exit(1 if report(per_second_rms(sys.argv[1])) >= MAX_SILENT_RUN else 0)
