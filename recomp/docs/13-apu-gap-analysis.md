# 13 - APU gap analysis: everything missing from the MCPX audio path

This is the complete register of audio functionality that is **not** implemented
or wired in the runtime, with the evidence for each entry and a porting plan.
It is the follow-on to [12-runtime-defects-audit.md](12-runtime-defects-audit.md)
(symptom 2, causes C/D), and it exists because "missing in-game sound" is not one
bug: it is a stub in the middle of the hardware pipeline.

Authoritative references are **xemu** (`hw/xbox/mcpx/apu/`) and **MAME**
(`xbox_pci.cpp` + `dsp563xx`). Cxbx is deliberately excluded: its audio is also
incomplete, so it cannot be used to decide what "correct" is. Where a claim about
this title is made, it comes from a named symbol, XBE section, or source line.

Scope: the `recomp/` runtime direction. The emulator direction at the repository
root is out of scope.

## 1. What the hardware is

The MCPX APU is three processors behind one 512 KB register window at
`0xFE800000`:

| Block | What it is | Rate | Runtime state |
|---|---|---|---|
| **VP** (Voice Processor) | 256 hardware voices: Xbox-ADPCM/PCM decode, pitch, envelopes, per-voice IIR, HRTF, 32 mixbins | 32 samples/frame (48 kHz) | **implemented** |
| **GP** (Global Processor) | DSP56362 (10 MHz) running the title-downloaded effects program (reverb, EQ, HRTF/submix) | 32 samples/frame | **stub** |
| **EP** (Encode Processor) | DSP56362 (10 MHz) final mixdown/encode; on real HW also AC-3/DTS | 256 samples / 8 frames | **stub** |

Signal flow: guest DirectSound voices → VP mixbins → **GP DSP** → **EP DSP** →
EP output FIFO 0 → AC'97 DAC. The runtime short-circuits the middle and replaces
it with a host mixdown.

## 2. How StarCraft: Ghost uses it

The title does **not** import an audio library. It statically links its own
DirectSound and XACT engines and drives APU MMIO directly:

- XBE sections: `[3] DSOUND` (`0x002F16A0`), `[4] XACTENG` (`0x0030FCA0`)
  (`logs/runtime-20261007-154931.log:19-20`).
- No `DirectSound*`/`XACT*`/`XAudio*` entry exists in
  `recomp/symbols/ghost.kernel_imports.txt` (138 imports, zero audio).
- Guest effects-image download chain (confirmed in the generated code):
  `LoadDSPImage_001462F0` (`recomp_0029.c:302`) →
  `IXACTEngine_DownloadEffectsImage_20_0030FCBE` (`recomp_0029.c:361`) →
  `DirectSound_CDirectSound_DownloadEffectsImage_002F1A87` (`recomp_0062.c:13400`) →
  `DirectSound_CMcpxAPU_DownloadEffectsImage_002F18FC` (`recomp_0062.c:12934`) →
  `DirectSound_CMcpxGPDspManager_DownloadEffectsImage_002F585D`
  (`recomp_0062.c:12948`).
- Guest symbols present: `DirectSound_CMcpxAPU_DownloadEffectsImage_002F18FC`,
  `DirectSound_CDirectSoundSettings_SetEffectImageLocations_002F1A0E`,
  `DirectSound_CHRTFSource_*` (`ghost.names.txt`).
- The DSP program ships in the game directory as `nsidsp.bin` and
  `dsstdfx.bin` (24936 bytes each, byte-identical).

Consequence: everything the title does to the GP/EP (program download, scratch
DMA, FIFOs, reset, doorbell) lands on registers the runtime either stores
blindly or ignores, and the host output is a surrogate.

## 3. Current implementation inventory

| Piece | File | State |
|---|---|---|
| Public API | `src/apu/apu.h` | complete for VP + software mixer |
| VP (voices, ADPCM, HRTF, SVF) | `src/apu/apu_vp.c` (1247 LOC) | implemented |
| APU core, frame thread, MMIO, XAudio2/waveOut | `src/apu/apu_core.c` | implemented for main+VP registers |
| Register defs (incl. GP/EP FIFOs, DSP mem windows) | `src/apu/apu_regs.h:79-127,322` | **defined but unused** |
| DSP core state structs (`dsp_core_t`, `DSPState`, `DSPDMAState`) | `src/apu/apu_state.h:43-139` | **structs only, no engine** |
| GP/EP "implementation" | `src/apu/apu_dsp.c` (257 LOC) | **passthrough stub** |
| MMIO trap | `src/kernel/xbox_memory_layout.c:2631` | traps only `0x0..0x30000` |
| MMIO dispatch | `src/apu/apu_core.c:795-814` | `GP (0x30000) and EP (0x50000) regions ignored for now` |
| DirectSound HLE | `src/audio/dsound_device.c` | stub, dead code for this title |
| WMA decoder | `src/audio/wma_decoder.c` | Windows only |
| XAudio2 host backend | `src/apu/apu_xaudio2.c` | Windows only; Linux inert |

The DSP state struct (`apu_state.h:43-102`) is already a full copy of xemu's
`dsp_core_t` (XRAM 4096, YRAM 2048, PRAM 4096, mixbuffer, peripherals,
interrupt state). What is missing is the code that executes it.

## 4. Gap register

Severity: **P0** required for correct in-game audio, **P1** required for faithful
output, **P2** host/portability, **P3** polish.

### P0 - the DSP is absent

**G1 - GP DSP56300 interpreter.** No DSP56300 CPU exists. `mcpx_apu_dsp_init`
(`apu_dsp.c:148`) allocates two `DSPState` structs and never runs them;
`mcpx_apu_dsp_frame` (`apu_dsp.c:172`) is the mixdown hack. The title's effects
program is therefore never executed.
Reference: xemu `hw/xbox/mcpx/apu/dsp/` - `dsp.c` (init/reset/bootstrap/run/
start_frame/halt/cycle), `dsp_c.c` (engine ops), `dsp/interp/dsp_cpu.c` +
`dsp/interp/dsp_emu.c.inc` (the ~3000-line instruction emulation),
`dsp/interp/dsp_cpu_regs.h`, `dsp_dis.c.inc`, `debug.c`.

**G2 - EP DSP56300 interpreter.** Same as G1 but the EP core; runs once per 8
frames. xemu `dsp/gp_ep.c` (`mcpx_apu_dsp_frame`: runs EP when
`ep_frame_div % 8 == 0`).

**G3 - GP/EP MMIO + DSP memory model.** `apu_core.c:813` explicitly ignores
`0x30000`/`0x50000`. Missing: GP `X/Y/P` windows and mixbuf
(`NV_PAPU_GPXMEM 0x0`, `NV_PAPU_GPMIXBUF 0x5000`, `NV_PAPU_GPYMEM 0x6000`,
`NV_PAPU_GPPMEM 0xA000`, `apu_regs.h:112-127`), EP windows
(`NV_PAPU_EPXMEM/EPYMEM/EPPMEM`), and the `GPRST`/`EPRST` reset registers.
Reference: xemu `gp_ep.c` `gp_read/gp_write/ep_read/ep_write`.

**G4 - GP/EP DMA (scatter-gather + circular FIFOs).** Missing:
`scatter_gather_rw` (GPSADDR/GPSMAXSGE, EPSADDR/EPSMAXSGE),
`circular_scatter_gather_rw`, `gp_fifo_rw` (4 out / 2 in FIFOs:
`NV_PAPU_GPOFBASE0 0x3024`.. and `GPIFBASE0 0x3064`..), `ep_fifo_rw`
(EPOFBASE0 `0x4024`.., EPIFBASE0 `0x4064`..). Reference: xemu `dsp/gp_ep.c`
and `dsp/dsp_dma.c`.

**G5 - DSP program bootstrap.** On GP/EP reset (write `0x3` to
`NV_PAPU_GPRST`/`EPRST` = `0x3FFFC`/`0x5FFFC`) the GP/EP scatter-gather tables
are walked and the program copied into DSP PRAM. Missing entirely; MAME documents
the mechanism (`xbox_pci.cpp`: reset `data & 0xf == 3` copies SGE-listed pages,
`& 0xFFFFFF`, into DSP program RAM). xemu: `proc_rst_write` → `dsp_bootstrap`.
This is the path `DownloadEffectsImage` depends on.

**G6 - DSP command/notify protocol.** The title hands the GP a command word and
spins until the DSP clears it. This is currently faked: `RECOMP_APU_DSP_ACK`
(`apu_dsp.c:112`) is forced to `gp:0x810` by `main.c:236-237`, and
`apu_core.c:630` clears the word once per frame. `NV_PAPU_FEMEMDATA` /
`FEMEMADDR` (`apu_core.c:215`) are stored but no notify completion is generated
from real DSP progress. A working GP makes this protocol real.

**G7 - VP → GP mixbuffer feed.** xemu writes all 32 mixbins into GP XRAM at
`GP_DSP_MIXBUF_BASE` (0x1400) each frame before running the GP
(`gp_ep.c` `mcpx_apu_dsp_frame`). The runtime writes nothing to the GP; it hands
the mixbins straight to the host mixdown.

**G8 - EP output path.** xemu routes EP output FIFO 0 into
`monitor.frame_buf` (`ep_sink_samples`). The runtime instead sums even bins to
left and odd bins to right (`apu_dsp.c:222-232`, default on via
`RECOMP_APU_MIXDOWN_ALL`). This is a surrogate: it ignores the GP/EP mixdown and
submix/headroom, and it is why effects and 3D positioning cannot be faithful.

### P1 - fidelity once the DSP runs

**G9 - DSP instruction coverage.** The engine must cover the full DSP56300 set;
xemu still had holes (`extractu #CO,S2,D`, xemu issue #108) and added
surround/AC-3 opcodes later (xemu PR #2865). Porting the interpreter alone is
not sufficient if a title's program uses an unimplemented opcode - the engine
must trap and report, not silently no-op.

**G10 - Interrupt scoring / IRQ delivery.** `MCPX_APU_ISTS` bits (GINTSTS,
FETINTSTS, FENINTSTS, FEVINTSTS; `apu_regs.h:27-31`) and `update_irq`
(`apu_core.c:110`) exist, but GP/EP-driven interrupt timing is not produced.
xemu's DSP raises guest interrupts at frame boundaries.

**G11 - AC'97 codec.** Only a "codec ready" bit is injected
(`xbox_memory_layout.c:2606-2646`). The real codec (reset/volume/mute registers
and the DAC that receives EP output) is not modelled. The runtime bypasses it
entirely and feeds XAudio2 - acceptable for output, but it means
`0xFEC00000` semantics are absent if a title reads them back.

**G12 - EP frame sync.** `ep_frame_div` drives the 8:1 EP cadence
(`apu_core.c:361,590`) and is reset on EPRST in xemu, but here EPRST is not
modelled, so the cadence is free-running rather than guest-synchronised.

### P2 - host and portability

**G13 - XAudio2 backend is Windows-only.** `apu_xaudio2.c:202-206` stubs every
entry on non-Windows, so the primary path is inert off Windows; only the
(also inert on Linux) waveOut fallback remains.

**G14 - waveOut fallback is Windows-only.** `apu_core.c:247-248` notes the Linux
`win32_compat.h` waveOut stubs never produce audio.

**G15 - WMA decoder is Windows-only.** `wma_decoder.c:239` returns a stub on
non-Windows, so any WMA-encoded wave is silent. Ties to `IXACTEngine` wave
banks if the title uses WMA (`fmt=A981E0E6` was seen for ADPCM).

### P3 - HLE surface and test

**G16 - DirectSound/XAudio2 HLE layer.** `xbox_DirectSoundCreate`
(`dsound_device.c:379`) is dead code for this title (the guest has its own
DSOUND). If any HLE path is ever used: `CreateSoundStream` returns `NULL`
(`:305`), all 3D methods and `SetMixBins` are no-ops (`:217-223`), `Lock` has no
wraparound (`:119-128`), `SetBufferData` copies instead of pointing, and
`GetCurrentPosition` reports the mixer cursor rather than a DMA cursor.

**G17 - No audio validation harness.** VP output is checked by `[APU-OUT]`
counters only. There is no golden-output test for the DSP, the mixdown, or the
downloaded effects program; "unmuted peak > 0" cannot tell a correct mixdown
from the surrogate.

## 5. Wiring gaps (not code, but where the stubs are made permanent)

- `main.c:234-237` force `RECOMP_AC97_READY=1` and `RECOMP_APU_DSP_ACK=gp:0x810`.
  These defaults turn the two diagnostic bypasses into the shipping
  configuration. `RECOMP_AC97_READY` also arms the MMIO trap
  (`xbox_memory_layout.c:2619,2631`), so it gates the whole emulated APU.
- `xbox_memory_layout.c:2631` traps only `XBOX_MCPX_APU_MMIO_SIZE` =
  `0x30000` (`xbox_memory_layout.h:50-52`). GP (`0x30000`) and EP are therefore
  plain RAM: guest writes are silent, reads return zero. This must widen (and
  route) when G3 lands; the aperture is 8 MB, so the space exists.
- `RECOMP_APU_MIXDOWN_ALL` defaults on (`apu_dsp.c:102-110`), so the surrogate
  mixdown is the default behaviour.

## 6. Port plan

**Phase 1 - DSP engine, no new features (P0).** Port xemu's
`dsp/dsp.c`, `dsp_c.c`, `dsp/dsp_dma.c`, `dsp/interp/*` into `src/apu/dsp/`,
reusing the existing `apu_state.h` structs and the `apu_shim.h` Win32 shims.
Add a `dsp_core.c`-style engine with `dsp_init/reset/bootstrap/start_frame/run/
halt`. Gate on a new `RECOMP_APU_DSP` (default off) so the stub remains the
fallback until validated. Replace `mcpx_apu_dsp_frame` with xemu's: write VP
mixbins to GP mixbuf, run GP each frame, run EP every 8th, route EP FIFO 0 to
`monitor.frame_buf`. Remove the even/odd mixdown from the DSP path.

**Phase 2 - registers and DMA (P0).** Model GP/EP MMIO + DSP memory windows
(G3) and DMA (G4), and wire the bootstrap reset (G5). Widen the MMIO trap (G17/
wiring). This is what makes `DownloadEffectsImage` actually load `nsidsp.bin`.

**Phase 3 - protocol and interrupts (P0/P1).** Let the real DSP answer the
command doorbell (retire G6 and the `RECOMP_APU_DSP_ACK` default), and produce
GP/EP interrupt timing (G10, G12).

**Phase 4 - fidelity and host (P1/P2).** Instruction coverage audit against the
title's actual program (G9), AC'97 readback (G11), and a portable host sink
(G13-G15). Cxbx is not the reference; validate against xemu and MAME, and by
ear.

**Phase 5 - validation (P3).** Add a DSP smoke test (known microcode → known
output) and a mixdown test, so G17 stops being a counter.

## 7. Open questions

1. Does the title's in-game path use GP effects only, or does it also use the
   EP? `ep_frame_div` and EPRST writes tell us; the log does not yet record them.
2. Which DSP program does this title download - `nsidsp.bin` (24936 B) - and does
   xemu's interpreter cover every opcode it contains? Disassemble it first.
3. Was "completely missing in-game sound" (doc 12) the surrogate mixdown
   (cause C) or the absent DSP (cause D)? The `WATCH=1 RECOMP_APU_DIAG=1` run is
   the discriminator: `[APU-OUT] voices`/`nonzero` in-mission.
4. Is `xemu`'s engine fast enough as a C interpreter, or is the JIT
   (`dsp_jit.c`, Rust) required? The GP runs 32 samples/frame at 48 kHz; measure
   before deciding.

## 8. References

Source (in tree):
- `src/apu/apu_dsp.c` (stub), `src/apu/apu_state.h:43-139` (DSP structs),
  `src/apu/apu_regs.h:79-127,322` (GP/EP registers),
  `src/apu/apu_core.c:110,215,359,560,630,795-814,837`,
  `src/apu/README.md:56-82`.
- `src/kernel/xbox_memory_layout.c:2557-2656,50-52`,
  `recomp/game/src/main.c:234-237,311-320`.
- `src/audio/dsound_device.c`, `src/audio/wma_decoder.c`, `src/apu/apu_xaudio2.c`.
- Guest: `recomp/symbols/ghost.names.txt`,
  `recomp/game/src/recomp/gen/recomp_0029.c:302`, `recomp_0062.c:12934,13400`.
- Cross-reference: [12-runtime-defects-audit.md](12-runtime-defects-audit.md)
  symptom 2.

Upstream references:
- xemu `hw/xbox/mcpx/apu/`: `apu.c`, `dsp/dsp.c`, `dsp/dsp_c.c`,
  `dsp/dsp_dma.c`, `dsp/gp_ep.c`, `dsp/interp/dsp_cpu.c`, `dsp/interp/dsp_emu.c.inc`.
- xemu issue #108 (`extractu`), PR #2801 / #2865 (JIT, surround/AC-3 opcodes).
- MAME `xbox_pci.cpp` (DSP56362 GP/EP, SGE program copy on reset).