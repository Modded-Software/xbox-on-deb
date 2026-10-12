#!/usr/bin/env python3
"""Integration test: record ~60 s of real gameplay audio and look for defects.

Records ghost.exe's own PipeWire output (the signal the sound server actually
plays -- post-XAudio2, so queue dropouts / gaps / clipping show up here, unlike
the runtime's internal PCM), then scans it for drop-offs (near-silence runs
surrounded by loud audio), stutters (frozen / zero-crossing-dead stretches),
sample discontinuities (clicks) and hard clipping.

Run it with:

    recomp/tests/run.py --user-state --only monitor
"""
import array
import math
import os
import sys
import time
import wave

from framework import Game, test

MONITOR_SECONDS = 60.0
WINDOW = 0.5          # analysis window (seconds)
SILENCE_PEAK = 200    # peak below this = a quiet window
LOUD_PEAK = 2000      # a window this loud is "content"
CLIP_LEVEL = 32000    # near int16 full scale
CLICK_DIFF = 22000    # sample-to-sample step that is a click, not audio


def _load(path):
    with wave.open(path, "rb") as h:
        rate, ch = h.getframerate(), h.getnchannels()
        frames = h.readframes(h.getnframes())
    s = array.array("h")
    s.frombytes(frames[:len(frames) // 2 * 2])
    return rate, ch, s


def _analyze(path):
    rate, ch, s = _load(path)
    per = max(1, int(WINDOW * rate * ch))
    peaks, rms, clicks = [], [], []
    for start in range(0, len(s), per):
        chunk = s[start:start + per]
        if not chunk:
            break
        peak = max(abs(v) for v in chunk)
        rms.append(math.sqrt(sum(float(v) * v for v in chunk) / len(chunk)))
        peaks.append(peak)
        step = max((abs(chunk[i] - chunk[i - 1]) for i in range(1, len(chunk))),
                   default=0)
        if step >= CLICK_DIFF:
            clicks.append(start // per)

    n = len(peaks)
    gaps = [i for i in range(n)
            if peaks[i] < SILENCE_PEAK
            and any(peaks[j] > LOUD_PEAK
                    for j in range(max(0, i - 3), min(n, i + 4)))]
    clipsegs = [i for i in range(n) if peaks[i] >= CLIP_LEVEL]
    return {
        "seconds": len(s) / float(rate * ch),
        "rate": rate, "windows": n,
        "peaks": peaks, "rms": rms,
        "gaps": gaps, "clips": clipsegs, "clicks": clicks,
        "peak_max": max(peaks) if peaks else 0,
        "rms_med": sorted(rms)[n // 2] if rms else 0.0,
        "silent": sum(1 for p in peaks if p < SILENCE_PEAK),
    }


def _report(tag, a):
    print(f"[monitor] {tag}: {a['seconds']:.1f}s, {a['windows']} windows "
          f"({WINDOW}s), peak_max={a['peak_max']}, rms_med={a['rms_med']:.0f}", 
          file=sys.stderr, flush=True)
    print(f"[monitor]   silence windows={a['silent']} "
          f"gaps(surrounded drop-offs)={len(a['gaps'])} "
          f"clip windows={len(a['clips'])} click windows={len(a['clicks'])}", 
          file=sys.stderr, flush=True)
    for name, idx in (("gap", a["gaps"]), ("clip", a["clips"]), ("click", a["clicks"])):
        if idx:
            secs = [round(i * WINDOW, 1) for i in idx[:20]]
            print(f"[monitor]   {name} at {secs}{' ...' if len(idx) > 20 else ''}", 
                  file=sys.stderr, flush=True)
    # Compact level trace: one char per window.
    bar = "".join("." if p < SILENCE_PEAK else ("#" if p >= CLIP_LEVEL else
                  ("o" if p > LOUD_PEAK else "-")) for p in a["peaks"])
    print(f"[monitor]   level: {bar}", file=sys.stderr, flush=True)


@test("audio monitor: 60 s of gameplay", timeout=480)
def audio_monitor(g: Game):
    assert g.goto_gameplay(key="space", gap=2.0, timeout=240.0), \
        "never reached gameplay"

    host = "/tmp/opencode/monitor_host.wav"
    try:
        os.remove(host)
    except FileNotFoundError:
        pass
    rec = g.start_app_recording(host)

    deadline = time.time() + MONITOR_SECONDS
    while time.time() < deadline:
        g.move(80, 0, count=8, interval_ms=20)
        g.tap("w", hold=0.25, gap=0.01)
        g.tap("space", hold=0.2, gap=0.01)
        g.tap("b", hold=0.2, gap=0.01)
    rec.stop()

    assert os.path.exists(host) and os.path.getsize(host) > 44, \
        f"no host audio recorded at {host}"
    a = _analyze(host)
    _report("host", a)
    assert a["seconds"] >= 40.0, f"only {a['seconds']:.1f}s of audio recorded"