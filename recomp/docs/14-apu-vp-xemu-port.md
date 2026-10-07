# 14 - APU VP / output: faithful xemu port

Status: implementing. Companion to `13-apu-gap-analysis.md` (gaps G1-G20).

## Goal

Make in-mission and menu audio work by replacing the simplified APU Voice
Processor and output pacing with xemu's implementations. The DSP56200 core and
`gp_ep.c` are already byte-identical to xemu; the divergences are all in the
Voice Processor (`apu_vp.c`) and the host output path (`apu_core.c`).

Context: rendering corruption was root-caused to the two-arena physical-address
collision and fixed (heap at 64 MB + `xbox_DmaPhysicalPointer` >=64 MB ordinary
RAM). FMV audio already plays; hardware voice audio (menu/mission) is silent.

## Confirmed gaps (report)

### Voice Processor (`apu_vp.c` vs xemu `vp/vp.c`)

| # | Area | xemu | ours (before) |
|---|------|------|----------------|
| V1 | Resampler | libsamplerate `src_callback_new(voice_resample_callback, SRC_SINC_FASTEST)` + `src_callback_read(rate, ...)` | naive linear interpolation (`voice_resample_fill`/`voice_resample`); `src_*` were stubbed in `apu_shim.h` |
| V2 | Voice scheduling | `voice_work_enqueue` -> `voice_work_schedule` (topologically groups multipass producers before consumers) -> `voice_work_dispatch` over `voice_worker_thread`s | single-threaded, list order; `voice_list` unused (`(void)voice_list`) |
| V3 | Multipass | `get_multipass_samples`, `peek_ahead_multipass_bin`, `dump_multipass_unused_debug_info`; producer/consumer ordering | inline mp-bin read, no ordering |
| V4 | HRTF | config-driven | `g_config.audio.hrtf = false` hardcoded |

The decisive bug is V2/V3: a multipass consumer voice reads its mixbin before the
producer voices have written it, so the submix is silence.

### Output / controller (`apu_core.c` vs xemu `apu.c`)

| # | Area | xemu | ours (before) |
|---|------|------|----------------|
| C1 | Pacing | time pacing + queued-bytes watermark throttle (`queued_bytes_low`/`high`, drift correction toward midpoint) | time pacing only |
| C2 | Extra path | none | `mixer_render` HLE DirectSound mixer straight into `frame_buf` (kept; FMV audio may use it) |

Decision: keep the native XAudio2 sink (already proven to output, native under
Proton/Wine) and lift xemu's *pacing algorithm* onto it. Porting SDL3 into the
zig-mingw build is new build risk with no fidelity gain.

## Implementation

### 1. Vendor libsamplerate 0.2.2 (BSD-2)

`refs/xboxrecomp/src/apu/third_party/samplerate/` gets the unmodified upstream
sources plus a hand-written `config.h`:

- `samplerate.c` (API incl. `src_callback_new/read`, `src_float_to_short_array`)
- `src_sinc.c`, `src_linear.c`, `src_zoh.c`
- `common.h`, `fastest_coeffs.h`, `mid_qual_coeffs.h`, `high_qual_coeffs.h`
- `samplerate.h`
- `config.h` (authored: little-endian, `HAVE_LRINT(F)`, all three SINC
  converters enabled, `SIZEOF_LONG 4` for Windows LLP64)
- `COPYING`

### 2. Build

`src/apu/CMakeLists.txt`: add the four `.c` files to `xbox_apu` and add the
vendored dir to the include path.

### 3. Shim

`apu_shim.h`: delete the libsamplerate stub block; `#include "samplerate.h"`.
The real `SRC_STATE`, `SRC_SINC_FASTEST`, `src_*` API now resolve at link time.

### 4. `apu_vp.c`

Port from xemu `vp.c`, adapting only the memory accessor
(`d->ram_ptr` -> `mcpx_apu_ram_address`) and keeping existing diagnostics:

- Replace linear resampler with `voice_resample_callback` + `voice_resample`.
- Add `get_multipass_samples`, `peek_ahead_multipass_bin`,
  `dump_multipass_unused_debug_info`, `get_voice_bin_src_dst`.
- Add worker-based dispatch: `voice_worker_thread`, `voice_work_enqueue`,
  `voice_work_schedule`, `any_queued_voice_locked`, `voice_work_dispatch`,
  `voice_work_init`, `voice_work_finalize`.
- `voice_process` gains the multipass path, active re-check, and the
  `voice_list`-aware VP-monitor mix (skip multipass sub-voice double count).
- `mcpx_apu_vp_frame` enqueues then `voice_work_dispatch`es.
- `mcpx_apu_vp_init/finalize` call `voice_work_init/finalize`; reset matches xemu.

### 5. HRTF

`g_config.audio.hrtf` defaults to true, overridable via `RECOMP_APU_HRTF=0`.

### 6. Output pacing

`apu_core.c` `throttle()` gains the queued-bytes watermark logic on top of the
XAudio2 submission. `xa2_submit_samples` already returns 0 when the queue is
full, so the watermark is derived from XAudio2's queued buffer count.

## Verification

- Build `ghost.exe`, run `scripts/18-launch-user.sh`.
- Confirm menu + in-mission audio, and that the previously fixed render is intact.
- Watch `[APU-OUT]`/`[APU-VOICE]` counters and libsamplerate `src error` output.

## Risks

- Worker init must run exactly once and be torn down; reset currently only reset
  the resamplers.
- The `voice_work_schedule` asserts encode Xbox-software assumptions
  (MP bin constant, MP voice clears its bin, MP sources consecutive). Release
  builds with `NDEBUG` drop them, but keep `RECOMP_DSP_ASSERTS` off for VP for now
  and watch for assert storms if enabled.
- `mixer_render` remains; it may mix on top of the VP output. If FMV needs it,
  leave it; otherwise gate it.