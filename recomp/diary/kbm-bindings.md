# Diary — KBM key bindings

## 2026-10-10 — rebind Y + stick clicks
- Changed: `refs/xboxrecomp/src/input/xinput_device.c` (`kbm_state`).
  - Gamepad **Y**: was key `R`; now the **right mouse button** (index 1).
    `k_y` default set to 0 (no key). White keeps Q or right-mouse.
  - **Left stick click**: key `R` (new `k_lthumb`, bindable as `LTHUMB`).
  - **Right stick click**: **middle mouse button** (index 2) (new `k_rthumb`,
    default 0, bindable as `RTHUMB`).
  - `kbm_binds` gained `LTHUMB`/`RTHUMB`; the profile line prints both.
- Command: `bash recomp/game/build.sh` then
  `SESSION=kbmbind bash scripts/18-launch-user.sh`
- Result: launched 720p KBM; log `logs/runtime-20261010-203140.log`. Profile
  line: `A=32 B=69 X=70 Y=0 BLACK=16 WHITE=81 LT=17 START=9 BACK=27
  LTHUMB=82 RTHUMB=0`. Bindings active; no errors counted (input-only change).
- GPU/error counts: not the focus; render path unchanged from R8.
## 2026-10-10 — scroll aliases left stick up/down
- Changed: `kbm_state`. Mouse wheel now also drives the left stick Y
  (`sThumbLY = ±32767` on non-zero wheel), in addition to the existing d-pad
  up/down alias. Read then overrides the W/S axis for that poll.
- Command: `bash recomp/game/build.sh`;
  `SESSION=kbmbind2 bash scripts/18-launch-user.sh`
- Result: launched; log `logs/runtime-20261010-203344.log`. Input-only change;
  render path unchanged from R8.

## 2026-10-10 — right-mouse split + scroll latch
- Changed: `kbm_state`. White no longer reads the right mouse button; it is key
  `G` (was Q). So right mouse now does only Y. Scroll->left-stick was a
  single-poll pulse the title barely integrated, so the deflection is now
  latched 150 ms after the last notch (`wheel_dir`/`wheel_until`).
- Command: `bash recomp/game/build.sh`;
  `SESSION=kbmbind3 bash scripts/18-launch-user.sh`
- Result: launched; log `logs/runtime-20261010-203626.log`. Profile:
  `A=32 B=69 X=70 Y=0 BLACK=16 WHITE=71 LT=17 START=9 BACK=27 LTHUMB=82
  RTHUMB=0` (WHITE=71_temp 'G', LTHUMB=82 'R', Y=0/RTHUMB=0 = mouse).
