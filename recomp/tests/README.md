# Automated tests

A small stdlib-only framework that drives the recompiled game from outside:
it launches (or attaches to) `ghost.exe`, injects X11 input via XTEST, and
asserts on observable state. Nothing here needs a human at the keyboard, and
nothing needs a build step beyond `recomp/game/build.sh`.

## Run it

```bash
recomp/tests/run.py                 # launch the game, run every test
recomp/tests/run.py --attach        # use an already-running game (fast loop)
recomp/tests/run.py --only dpad     # only tests whose name contains "dpad"
recomp/tests/run.py --scene         # print the current scene fingerprint
recomp/tests/run.py --scene --record  # append it to baselines/scenes.txt
```

## Layout

| File | Purpose |
|---|---|
| `xinject.py` | Inject X11 key/button/mouse events via XTEST (ctypes; no compiler). Also `list`/`focus`/`title`/`wait` to find and focus the game window. |
| `framework.py` | `Game` (launch/attach, inject, read telemetry) and the `@test` registry/runner. |
| `test_*.py` | Test modules; importing them registers their cases. `test_input.py` (keys/sticks/d-pad), `test_mouse.py` (input-layer mouse), `test_zzz_gameplay.py` (drives into a mission; sorts last). |
| `run.py` | Discovers `test_*.py`, starts one game, runs the tests, reports. |
| `baselines/` | Recorded scene fingerprints (created by `--record`). |

## Feedback channels

A test can observe five things, which is what makes it able to say *what
happened*, not just "no crash":

1. **Input state** — `Game.wait_input()` returns the runtime's `[INPUT]`
   diagnostic (window saw the key? synthesized buttons/sticks/pressure?).
   This is the `RECOMP_INPUT_DIAG=1` line, sampled once per second.
2. **Key edges** — `Game.key_trace()` returns the window's `[KEY]` log
   (`RECOMP_KEY_TRACE=1`), which catches taps the 1 Hz sampler misses.
3. **Liveness** — `Game.frame()` / `fps()` read the window caption
   (`Frame N`, `FPS`), so a frozen game is distinguishable from a live one.
4. **Pixels** — `Game.capture_hash()` triggers the built-in F12 framebuffer
   dump (`RECOMP_FB_CAPTURE`) and hashes it. Use it to assert the *scene*
   changed after input, or to fingerprint "where in the game" you are.
5. **GPU health** — `Game.shader_failures()`, `texture_failures()` and
   `cpu_fallback_batches()` parse the periodic `[GPU-D3D11]` summary, so a
   scene that fails to compile a shader or decode a texture fails a test
   instead of just looking wrong.

## Adding a test

```python
from framework import Game, test, hold, START

@test("Start pauses the game")
def start_pauses(g: Game):
    sample = hold(g, "Tab", expect={"buttons": START})   # press, sample, release
    assert sample["buttons"] & START, sample
```

`hold()` presses a key and keeps it down until a fresh `[INPUT]` sample
satisfies `expect` (a bitmask is ANDed), then releases. The default KBM layout
is `Return`=A, `E`=B, `space`=X, `Tab`=Start, `Esc`/`BackSpace`=Back; see
`src/input/xinput_device.c` and `docs/08-input.md`.
For scene checks, hash before and after:

```python
before = g.capture_hash()
g.key("Return", "press")
assert g.capture_hash() != before
```

## Notes

- The framework hides Wine's console window and the runtime calls
  `SetForegroundWindow`/`SetFocus` on the framebuffer window, because the
  console-subsystem exe otherwise keeps keyboard focus and the game sees no
  keys. Tests still call `Game.focus()` first as a belt-and-suspenders.
- `Game.stop()` kills the process group it launched (`start_new_session=True`),
  so a failed test does not leak a running game.
- The injector is a general X11 tool; keep game-specific knowledge in
  `test_*.py`.
