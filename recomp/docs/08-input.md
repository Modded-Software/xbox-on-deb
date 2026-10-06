# 08 — Controller, Keyboard and Mouse Input

Research and design for (a) full Xbox-controller support and (b) an optional
keyboard+mouse mode gated behind a `--kbm` executable flag. No code is changed
by this document; it records the evidence, the current state, the gaps, and the
plan.

## Goal

1. **Full Xbox-controller support** — a physical XInput pad drives the game
   through the same path the console's XAPI uses, including all four ports
   where the toolkit allows, force feedback, and live connect/disconnect.
2. **Keyboard + mouse**, off by default, enabled with `--kbm` on `ghost.exe`.
   Keyboard drives movement/actions; mouse drives the camera/aim stick. The
   existing `RECOMP_KEYBOARD` overlay is not this — see gaps.

## The input chain, end to end

### Guest side (recompiled StarCraft: Ghost)

The title does not call a host input API. It carries the Xbox XAPI USB/XID
stack statically linked, in the XPP section, and reads the pad through the Xbox
Peripheral Port:

```
game logic  ->  XReadGamepad / stdInput_*  ->  XID_Init / USBHUB_Init /
                USBD_* / IUsbDevice_* (XPP section)  ->  OHCI registers + IRQ
                ->  (runtime) usb_gamepad_report()  ->  xbox_InputGetState()
                ->  XInput backend  ->  host pad
```

Guest symbols (from `recomp/symbols/ghost.names.txt`):

| VA | Symbol |
|---|---|
| `0x001B99C0` | `XReadGamepad` — the entry the game calls to sample the pad |
| `0x001B9670` | `stdInput_SetCurrentGamepad` |
| `0x0001C7B0` | `stdInput_GetAnalogJoyStick` |
| `0x0006B320` | `cControl_GetPlayerRelativeJoystick` |
| `0x00359C11` | `XID_Init_4` |
| `0x00359F12` | `USBHUB_Init_4` |
| `0x00359E1C` / `0x00359E95` | `USBD_Init_8` / `USBD_NewHostController_8` |
| `0x0035B8D0`+ | `USBD_AllocateMemory`, `IUsbDevice_*`, `USBD_DeviceEnum*` |
| `0x00020060` / `0x00021B90` | `CmdRumble` / `CmdDoRumble` — force feedback |

Those XPP addresses are why four of our seed functions
(`recomp/config/seed_functions.json`) were needed: `disasm` did not detect them,
so before seeding the USB/XID init never ran and the pad was never enumerated.

### Runtime side (`refs/xboxrecomp`)

- **Host mapping** — `src/input/xinput_device.c`.
  `xbox_InputGetState` reads a host `XINPUT_STATE` and rewrites it into the
  Xbox `XBOX_INPUT_STATE` layout: digital flags (`wButtons`), the six analog
  face buttons plus two triggers (`bAnalogButtons[8]`), and four stick axes.
  Legacy mapping (README):
  A/B/X/Y→A/B/X/Y, Black→LB, White→RB, LT/RT→triggers, Start→Menu,
  Back→View, d-pad→d-pad, stick clicks→L3/R3.
- **Configuration** — env, parsed once by `xbox_InputInit`:
  `RECOMP_XINPUT_SLOT`, `RECOMP_INPUT_MAP`, `RECOMP_INPUT_THRESHOLD`,
  `RECOMP_INPUT_DEADZONE_LEFT/RIGHT`, `RECOMP_INPUT_AXES`, `RECOMP_KEYBOARD`.
- **USB gamepad** — `src/usb/usb_gamepad.c` presents a Controller S
  (VID 0x045E, PID 0x0289, interface class 0x58/0x42) with a 20-byte XID input
  report built from `xbox_InputGetState(0)`; it answers XID descriptor and
  capability requests. `usb_gamepad_report()` is the layout canonical
  reference (`usb_gamepad.c:280`).
- **OHCI** — `src/usb/ohci.c` traps `0xFED00000`/`0xFED08000`, runs the ED/TD
  lists, and calls `usb_gamepad_report()` for the interrupt IN endpoint.
  Keyboard/APU/OHCI register faults are routed through the VEH in `main.c`.
- **Window** — `src/video/fb_present.c` is the visible display window
  (`XboxRecompFramebuffer`, `fb_wndproc`). It tracks `s_key_down[256]` and
  exposes `xbox_FramebufferKeyDown(vk)` (`fb_present.c:117`). The NV2A executor
  opens it on the first clear (`nv2a_pb_exec.c:914`). This is the window that
  has focus and receives keys, so it is also where mouse handling must live.

### Runtime evidence from our build

`recomp/game/recomp_boot.log` (the working run):

```
[XINPUT] profile: slot=-1 (-1=auto) threshold=30 deadzones=0/0 axes=0
[XINPUT] live controller discovery enabled
OHCI: two controllers at 0xFED00000 and 0xFED08000, 2 ports each, one device on HC0 port 1
[OHCI0] operational after 3340 ms; device arriving on port 1
[OHCI0] periodic list enabled (HcControl=000000BE HCCA=00BEA000)
[OHCI0] raised 00000002 -> ISR claimed it      (repeated)
[FBWIN] framebuffer window open (640x480)
```

So the pad is enumerated by the guest's XAPI stack, the periodic list runs, and
the guest ISR consumes the interrupts. The physical-pad path is live.

## Current state

| Capability | State | Evidence |
|---|---|---|
| Physical XInput pad, port 0 | Works | OHCI enumeration + ISR in boot log |
| Direct API (ports 0–3) | Implemented | `xinput_device.c:273` `poll_host` |
| Analog buttons / triggers / sticks | Implemented | `xinput_device.c:292` |
| Remap / deadzone / threshold / axes | Implemented | `xinput_device.c:56` |
| Rumble (host ← guest) | Implemented (layout unconfirmed) | `usb_gamepad_output`, `ohci.c` OUT |
| Four independent USB pads | **Not modelled** | input README: one virtual gamepad |
| Keyboard | Probe (`RECOMP_KEYBOARD`) + KBM | `xinput_device.c` `keyboard_state` |
| Mouse | Implemented | `fb_present.c` mouse API, `kbm_state` |
| `--kbm` flag | Implemented | `main.c` parses `argv` → `RECOMP_KBM`; launcher `KBM=1` |

### Gaps, precisely

1. **Rumble is dropped.** `ohci.c:575-580` accepts and discards OUT data, so a
   guest `XInputSetState`-equivalent (the XID output/rumble report the game's
   `CmdRumble` path drives) never reaches `xbox_InputSetState`, even though the
   host function exists and works (`xinput_device.c:339`).
2. **One virtual gamepad.** The OHCI model exposes a single Controller S; the
   direct path can address four ports but the USB path cannot. Four-player
   local is therefore out of scope without more OHCI device models.
3. **Keyboard is a bring-up probe, not a control scheme.** It uses a
   Dreamcast/Saturn-style fixed map (`arrows`/`Z X A S`/numpad + `I J K L`),
   merges only onto port 0, and is enabled by `RECOMP_KEYBOARD`, not a flag.
4. **No mouse** in the window or the input layer.
5. **Possible untranslated USB callbacks.** The input README warns that seeded
   discovery can miss USB-class/XID registry callbacks; the runtime icall
   feedback loop (`tools/recomp/icall_feedback.py`) is the mechanism to close
   this.

## Design — full controller support

Small, surgical; most of it exists.

1. **Keep the OHCI path** (already wired in `main.c`: `xbox_InputInit`,
   `xbox_OhciInit`, `RECOMP_USB=1`, `RECOMP_USB_NDP=2`).
2. **Rumble**: in `ohci.c`, when an OUT transfer targets the pad's interrupt
   endpoint, decode the XID output report (2-byte left/right actuator, scaled
   to 0–65535) and call `xbox_InputSetState(0, ...)` instead of discarding.
   Record as a toolkit patch (like `xboxrecomp-mmio.patch`).
3. **Reachability**: after a live pad session, harvest unresolved ICALL targets
   with `tools.recomp.icall_feedback.py`, merge, and add any USB/XID/report
   entry points to `recomp/config/seed_functions.json`; re-run the seeded
   pipeline. Guard against truncating functions (the tool aligns/filters).
4. **Four ports**: document the one-pad limit; the direct path already supports
   four if a title ever uses it.

## Design — `--kbm`

### Flag → seam

`ghost.exe` is console-subsystem, so `main(argc, argv)` runs and calls
`WinMain`. Parse `argv` for `--kbm` in `main.c` (game project, committed) and
set an environment seam the toolkit already reads, e.g.
`RECOMP_KBM=1` (and force `RECOMP_KEYBOARD=0`). Implemented in the game project;
the toolkit backend is a recorded patch.

### Keyboard + mouse backend

Add to `src/input/xinput_device.c`, gated on `RECOMP_KBM` (patched toolkit),
used by both the direct and USB paths because both funnel through
`xbox_InputGetState`.

Default mapping (modern desktop, third-person action):

| Input | Xbox output |
|---|---|
| `W A S D` | left stick X/Y |
| mouse Δ | right stick X/Y (camera/aim) |
| left mouse | Right trigger (fire) |
| right mouse | Left trigger (aim) |
| `Space` | X (jump) |
| `Enter` | A (confirm/action) |
| `E` | B (use/interact) |
| `R` / `F` | Y / Black |
| `Q` | White |
| `Tab` / `Esc` (or `BackSpace`) | Start / Back |
| `1`–`4`, arrows | d-pad |
| mouse wheel | d-pad up/down |

Any face/back binding can be remapped without a rebuild with
`RECOMP_KBM_MAP="A=Space,B=E,X=Control,Y=R,START=Return,BACK=Escape"` (single
letters or the names `Return Space Tab Escape Back Shift Control Alt`).

Tuning knobs (env, consistent with the existing profile): `RECOMP_KBM_SENS`,
`RECOMP_KBM_INVERT_Y`, `RECOMP_KBM_DEADZONE`, `RECOMP_KBM_MAXDELTA`. Mouse
movement is accumulated between polls and cleared on read. Motion within a
pixel of the recentre point is discarded, because Wine lands the warped cursor
a pixel off centre and that residual leaks out as a constant slow drift.

### Mouse plumbing (the only genuinely new window code)

In `fb_wndproc` (`fb_present.c`), add `WM_MOUSEMOVE`, `WM_LBUTTONDOWN/UP`,
`WM_RBUTTONDOWN/UP`, `WM_MBUTTONDOWN/UP`, `WM_MOUSEWHEEL`, and
`WM_KILLFOCUS` (already clears keys). Track cursor position and buttons; expose
a small API alongside `xbox_FramebufferKeyDown`, e.g.:

```c
int xbox_FramebufferMouseDelta(int *dx, int *dy);
int xbox_FramebufferMouseButton(int which);   /* 0=L,1=R,2=M */
```

To make the camera usable, `--kbm` should clip/recentre the cursor while the
window is focused (`ClipCursor`/`SetCursorPos` to the window centre, hide the
cursor), releasing it on focus loss. Without this the pointer leaves the window
and the camera stops. This is the one behaviour that needs care under Wine.

### Where it must not go

Do **not** reimplement `xbox_InputGetState` in the game project: `usb_gamepad.c`
(the OHCI report source) links directly against the toolkit's symbol, so a
game-side duplicate is a link error and a game-side wrapper would be bypassed.

## Plan

1. **Docs** — this file; index it in `00-overview.md`. *(done with this doc)*
2. **Controller completeness** — rumble over OHCI; record toolkit patch;
   verify a live pad during a session; harvest ICALL targets and reseed.
3. **Mouse plumbing** — add mouse tracking/getters to `fb_present.c`; toolkit
   patch.
4. **KBM backend** — add the `RECOMP_KBM` synthesizer to `xinput_device.c`;
   toolkit patch.
5. **Flag** — parse `--kbm` in `main.c`, set the seam, update the launcher and
   `docs`.
6. **Verify** — physical pad reaches the menu; `--kbm` reaches the menu with no
   pad; rumble observed on the pad; boot log shows the KBM profile line.

## Host-side issue: X11 keyboard backlog (found during testing)

Symptom, seen with `--kbm` at the ~12 FPS menu scene: holding an arrow key
registers repeated presses, each arriving seconds late, and the release is
delayed in proportion to how long the key was held (5–10 s).

This is not the recompiled input path. It is the well-known Wine/Proton + X11
input-method bug: when Wine talks to the X input method (IBus/XIM), IBus replays
auto-repeat press events through the IM one at a time. When the frame/event rate
is below the key-repeat rate (e.g. 12 FPS vs 30 Hz repeat), the replayed events
and the final release back up in time. Reported for Wine/Proton in
`ValveSoftware/Proton#5294` and `ibus#2480`; the phrasing "pushing buttons 5–8
seconds ahead" appears verbatim in the WineHQ forum.

Proton disabled XIM historically, then re-enabled it in Proton 9.0 (so also in
GE-Proton 11, which we use) — which is why it surfaced now.

Fixes, in order of preference:

1. `PROTON_NO_XIM=1` (Proton's supported switch; leaves `WINE_ALLOW_XIM=0`).
   Set in `scripts/14-launch-recomp.sh`, so it applies to every run.
2. `IBUS_ENABLE_SYNC_MODE=2` (ibus hybrid-async) if a system still routes
   through IBus.
3. Disable GNOME "Repeat keys" / `xset r off` — the blunt fallback; confirms the
   diagnosis because it removes the repeats entirely.

The app's own message pump already drains the whole queue each frame
(`while (PeekMessageA(...))` in `fb_present.c`), so the backlog is in XIM/IBus,
not in the Win32 queue.

## Open questions / risks

- **Frame-rate coupling of the mouse.** Mouse deltas are polled by XAPI at the
  title's input rate; low FPS makes aiming coarse. Accumulate and scale by dt.
- **Focus under Proton.** The DXVK device and the GDI framebuffer window both
  exist; confirm the framebuffer window is the one under focus when `--kbm`
  runs, and that `ClipCursor` works under Wine. Evidence to capture:
  `RECOMP_KEY_TRACE` and `RECOMP_INPUT_DIAG` during a run.
- **Rumble report format.** Confirm the XID output report layout the game sends
  (the XID descriptor advertises `bMaxOutputReportSize` 6) before scaling.
- **One pad only** over USB; four-player needs more OHCI device models.
