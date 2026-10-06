# Toolkit patches

`xboxrecomp-mmio.patch` fixes the MMIO trap decoders so DirectSound/game
register accesses decode instead of faulting. Without it the recompiled build
crashes during boot (OHCI `HcFmInterval` read, then APU DSP mailbox `test`).

Two files in `refs/xboxrecomp` (gitignored, so recorded here):

- `src/platform/mmio_decode.h` — add the register-destination read forms
  (`AND/OR/XOR/ADD/SUB/CMP r, r/m`) and the immediate group (`80/81/83`) plus
  `TEST r/m, imm` (`F6/F7`), with a width-correct register store helper.
- `src/apu/apu_mmio_hook.c` — drop the APU's private opcode table and route
  through the shared decoder via `mcpx_apu_mmio_read/write` adapters.

`xboxrecomp-input-perf.patch` adds keyboard+mouse input, OHCI rumble, and the
performance/IRQL fixes. Disjoint from the MMIO patch, so order does not matter.
See `recomp/docs/08-input.md` and `recomp/docs/09-performance.md`.

- `src/input/xinput_device.c` — `RECOMP_KBM` keyboard+mouse overlay.
- `src/video/fb_present.c`, `src/video/video_player.h` — mouse capture + state.
- `src/usb/usb_gamepad.c/.h` — rumble output report + `RECOMP_INPUT_DIAG`.
- `src/usb/ohci.c` — route pad OUT reports to rumble; **enter guest ISRs at
  DISPATCH_LEVEL** and mirror into `fs:[0x24]` (fixes the 44k KeBugCheck storm).
- `src/kernel/kernel_bridge.c` — KeBugCheck caller + throttle, IRQL mismatch trace.
- `src/kernel/nv2a_gpu_d3d11.cpp`, `src/kernel/nv2a_gpu.h` — validate each
  texture once per frame (`RECOMP_TEX_VALIDATE_ONCE`); completion-only sync
  skeleton (`RECOMP_SYNC_LIGHT`, default off).
- `src/kernel/nv2a_pb_exec.c` — flush-reason counters.

Apply to a fresh toolkit clone:

```bash
bash recomp/patches/apply.sh /path/to/xboxrecomp
```

Reproduce a patch from a modified tree:

```bash
git -C refs/xboxrecomp diff > recomp/patches/xboxrecomp-mmio.patch
git -C refs/xboxrecomp diff -- <files> > recomp/patches/xboxrecomp-input-perf.patch
```

Reproduce the file from a modified tree:

```bash
git -C refs/xboxrecomp diff > recomp/patches/xboxrecomp-mmio.patch
```
