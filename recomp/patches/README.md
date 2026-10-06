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

Apply to a fresh toolkit clone:

```bash
bash recomp/patches/apply.sh /path/to/xboxrecomp
```

Reproduce the file from a modified tree:

```bash
git -C refs/xboxrecomp diff > recomp/patches/xboxrecomp-mmio.patch
```
