# 07 - ReShade integration: research and plan

Scope: how to bring **ReShade** (post-processing effects: colour grading, sharpening,
bloom, SMAA/FXAA, LUTs, CAS, etc.) to the **recomp path** (`ghost.exe` running under
GE-Proton), and a concrete phased plan. This is a design/research note; nothing here
is implemented yet.

> Reminder from `AGENTS.md`: graphical results are only *verified by the user*. The
> plan below ends with a hands-on verification step, not a screenshot.

---

## 1. Executive summary

ReShade is a present-time post-processor. It hooks a graphics API (D3D9/10/11/12,
OpenGL, Vulkan), intercepts the frame at **swap-chain present**, and runs its effect
chain on the back buffer. xboxrecomp does **not present gameplay through any swap
chain**: the NV2A native D3D11 backend renders offscreen, reads the frame back into
guest RAM, and a plain **GDI window blits that CPU buffer with `StretchDIBits`**.

So the blocker is not "which ReShade DLL", it is that **there is nothing for ReShade
to hook**. Stock ReShade injection cannot work until the game window presents through
a real graphics-API swap chain.

Two families of route (see §4 for the full table):

* **Route A (recommended): give the framebuffer window a real DXGI swap-chain
  presenter, then inject stock ReShade as a `dxgi.dll` proxy.** Smallest change,
  gives the whole ReShade ecosystem (all `reshade-shaders`, presets, the Home-key
  overlay). ReShade under Proton is supported with `WINEDLLOVERRIDES="dxgi=n,b"`.
  A′ is the same presenter but drives the effect runtime explicitly.
* **Route B (fully self-contained alternative): embed the ReShade FX compiler +
  effect runtime inside the native D3D11 backend** and run the chain on the presented
  surface texture before the CPU readback. No external DLL and no `WINEDLLOVERRIDES`,
  but it vendors a large C++ subtree and we own the effect runtime.

Recommended sequence: **Phase 1 (add the DXGI presenter) is worth doing
regardless** (it also gives GPU scaling/vsync and better performance than the
GDI blit). Then Phase 2 injects stock ReShade. If the DXVK/Proton proxy chain proves unreliable, the
the next choices are A′ (drive the ReShade runtime explicitly) then B (fully embed it).
Phase 1 is shared by every route.

---

## 2. What ReShade is (architecture)

Source: github.com/crosire/reshade (BSD-3-Clause; some files dual
BSD/MIT). Effect runtime flow: deepwiki.com/crosire/reshade/4.3-effect-runtime-flow.

ReShade is three separable pieces:

1. **ReShade FX**, a C-like shader language and a **standalone compiler**
   (`source/effect_*.cpp`: `effect_lexer`, `effect_preprocessor`, `effect_parser*`,
   `effect_symbol_table*`, `effect_codegen_*`). The project explicitly says it "can
   be integrated into other projects… add all `source/effect_*.*` files and use it
   similar to the `fxc` example" (`tools/fxc.cpp`). It targets DXBC, HLSL, GLSL and
   SPIR-V.
2. **The effect runtime** (`source/runtime.cpp`, `runtime_*`), loads `.fx` files,
   compiles techniques/passes, manages uniform variables, effect textures and the
   overlay. It is bound to **a `reshade::api::swapchain` + a command queue**:
   `reshade::runtime(api::swapchain*, api::command_queue*, …)`. It renders the chain
   into the **swap-chain back buffer** from `runtime::on_present()`.
3. **The injection/hook layer** (`source/dxgi/`, `source/d3d11/`, `source/vulkan/`…):
   proxy DLLs and vtable hooks. `source/dxgi/dxgi_swapchain.cpp` wraps
   `IDXGISwapChain`; its `Present`/`Present1` call `reshade::present_effect_runtime`
   before forwarding. `D3D11CreateDevice*` / `IDXGIFactory::CreateSwapChain` are
   hooked to build the proxy device/swap-chain.

Deployment form: a proxy DLL (`dxgi.dll`, `d3d11.dll`, `d3d9.dll`, `opengl32.dll`,
`vulkan-1.dll`) placed next to the `.exe`, plus `.fx` shaders and a preset. There is
also a **ReShade add-on API** (`include/reshade*.hpp`, header-only) for DLLs/embedded
code that want to use the API *when ReShade core is already loaded*.

### 2.1 The add-on API: explicit effect runtimes (important for us)

`include/reshade.hpp` (header-only; `RESHADE_API_VERSION 20`) exposes an API that lets
code **create an effect runtime for a swap chain ReShade did not auto-hook**:

```cpp
reshade::create_effect_runtime(reshade::api::device_api api,
                               void *device, void *command_queue, void *swapchain,
                               const char *config_path,
                               reshade::api::effect_runtime **out_runtime);
reshade::update_and_present_effect_runtime(reshade::api::effect_runtime *runtime);
reshade::destroy_effect_runtime(reshade::api::effect_runtime *runtime);
```

For D3D11 the opaque pointers are `ID3D11Device*`, `ID3D11DeviceContext*` and
`IDXGISwapChain*`. The header docs describe it as "for when it was not already hooked
by ReShade (e.g. because `RESHADE_DISABLE_GRAPHICS_HOOK` is set)". This is the escape
hatch for renderers ReShade cannot hook, provided there is a swap chain to bind to.

Two consequences for xboxrecomp:

* It does **not** remove the need for a swap chain (Phase 1 still stands).
* It lets us run ReShade **explicitly and only where we want**, apply the chain to
  the gameplay swap chain and drive `update_and_present_effect_runtime` ourselves,
  instead of relying on the auto-hook. Useful if auto-hook mis-detects or if we want
  effects off for FMV/UI. To use it, ReShade core must be resident (proxy DLL with
  `RESHADE_DISABLE_GRAPHICS_HOOK=1`), and the caller is typically a ReShade add-on
  (a small `AddonInit` DLL, or a ReShade `BUILTIN_ADDON` compiled into the DLL).

### ReShade on Linux / Proton

Verified by community reports (Proton issue #4079, #2908; DXVK issue #1057;
`nesdeq/reshade` installer):

* ReShade runs **under Proton + DXVK** as a **native `dxgi.dll`** with
  `WINEDLLOVERRIDES="dxgi=n,b"` (and sometimes `d3dcompiler_47=n`).
* Historically fragile with certain DXVK versions (1.2.x) and with Wine < 8.5
  (keyboard+mouse freeze, since fixed in Wine 8.5+/modern Proton). GE-Proton 11 is
  modern, so this should be fine.
* If `dxgi.dll` alone fails, the documented remedy is to also use the `d3d11.dll`
  proxy form. Which one is needed is title-specific.

---

## 3. How xboxrecomp presents today (the mismatch)

The gameplay present pipeline (recomp path), confirmed from a live log: the device
comes up as `[GPU-D3D11] device ready: feature level 0xB000`, the window is
`[FBWIN] framebuffer window open (1920x1080)`, and there is **no** `IDXGISwapChain`
`Present` for gameplay.

```
 guest title (Xbox D3D8 driver, recompiled)
        │ writes NV2A pushbuffers into guest RAM, kicks NV2A
        ▼
 refs/xboxrecomp/src/kernel/nv2a_pb_exec.c   (pushbuffer executor)
        │ draws via
        ▼
 refs/xboxrecomp/src/kernel/nv2a_gpu_d3d11.cpp   native D3D11 device (DXVK under Proton)
        │  Surface.texture  <-- the completed frame lives here
        │ on NV097_FLIP_STALL (nv2a_pb_exec.c:4255)
        ▼
 nv2a_gpu_flip()  (nv2a_gpu_d3d11.cpp:1692)
        │  stage_flip()/gpu_sync: CopyResource -> staging -> Map -> swizzle
        ▼
 guest framebuffer RAM  (published, because the guest reads it back)
        ▼
 xbox_FramebufferWindowPresent()  (fb_present.c:113)   copy into s_present[2]
        ▼
 fb_present.c:fb_thread()  (fb_present.c:909)  GDI window "XboxRecompFramebuffer"
        │  fb_gamma_apply -> StretchDIBits()  (fb_present.c:1061)  <-- SCREEN
        ▼
 screen (Wine X11 -> XPutImage)
```

Key facts:

* The **final present is `StretchDIBits`** (GDI, CPU), no D3D, no DXGI, no Vulkan
  present. ReShade has no hook point.
* The native D3D11 device (`nv2a_gpu_d3d11.cpp:3306`, `D3D11CreateDevice`) is created
  **without a swap chain**.
* The CPU readback is essential: the guest reads its framebuffer back through
  lock/fence, and the cloak/refraction effect samples the front buffer
  (`present_snapshot()` at `nv2a_gpu_d3d11.cpp:1556`). We must **not** remove it.
* The FMV path *does* use a D3D8→D3D11 swap chain (`d3d8_device.c:196`
  `D3D11CreateDeviceAndSwapChain`, `d3d8_present()` at `d3d8_device.c:123`,
  `video_pump.c:106`). A `dxgi` proxy would already post-process **intro videos**,
  just not gameplay.

The window and its message loop, raw input, recording/replay and KBM all live in
`fb_present.c`. Any new presenter must keep that window (HWND `s_fb_hwnd`) and its
input path intact.

---

## 4. Integration options

| # | Option | What it is | Effort | Gets full ReShade? | Notes |
|---|--------|-----------|--------|--------------------|-------|
| A | **DXGI presenter + stock ReShade proxy (auto-hook)** | Add an opt-in D3D11 swap-chain presenter for the framebuffer window; inject ReShade as `dxgi.dll` with `WINEDLLOVERRIDES="dxgi=n,b"`; let ReShade auto-hook | Low-medium | **Yes** (all shaders, presets, overlay, add-ons) | Relies on ReShade+DXVK proxy chain; known-working but historically finicky |
| A′ | **DXGI presenter + ReShade proxy, explicit runtime** | Same presenter, but ship ReShade with `RESHADE_DISABLE_GRAPHICS_HOOK=1` and create the runtime ourselves via `reshade::create_effect_runtime(d3d11, dev, ctx, swapchain, …)` from a small add-on (or `BUILTIN_ADDON`); drive `update_and_present_effect_runtime` at flip | Medium | Yes | Deterministic; we choose which swap chains/windows get effects; still uses the ReShade DLL (no big vendoring) |
| B | **Fully embed ReShade FX + runtime** | Vendor `source/effect_*` (+ D3D11 runtime), run the chain on `Surface.texture` inside `nv2a_pb_exec` before readback; output stays on the GDI path | High | Yes, but we host it (no overlay unless we build one) | BSD-3; no external DLL, no Wine overrides; we own pass/technique/uniform handling |
| C | CPU post-process on the GDI frame | Reimplement a few effects as CPU code | Low | No, only a hand-picked subset | Rejects the entire ReShade FX ecosystem; not "ReShade" |
| D | Vulkan layer (vkBasalt / dlss-on-arc style) | Capture at `vkQueuePresentKHR` | n/a | No | There is **no Vulkan present** for gameplay, so a layer has nothing to capture. Rejected |

**Recommendation: A, then A′ as the next choice, then B.** A is the least code and gives the
real product. A′ keeps the ReShade DLL/ecosystem but removes the dependence on
auto-hook behaviour (the historically fragile part). B is the last resort, no
external DLL, but we host the runtime. All three share Phase 1, so building the
presenter is the common, unavoidable first step and is independently useful.

---

## 5. Recommended plan

### Phase 0, Recon and guardrails (no code)

1. Confirm the present path per build with a fresh launch and grep the runtime log
   for `[FBWIN]`, `[GPU-D3D11] device ready`, `[GPU] presentation:`, and the absence
   of DXGI `Present` for gameplay. (Done for the current build; re-check after any
   runtime change.)
2. Record a baseline in `recomp/diary/reshade.md` per `AGENTS.md`: command,
   result, and error counts (`FAILED`, `error`, `WARN`, `rejected`, `unhandled`,
   `unsupported`, `[PB] desync`, `[CRASH]`).
3. Decide the switch: **keep GDI the default**; add an opt-in presenter so tests and
   recording/replay are unaffected unless requested.

### Phase 1, D3D11/DXGI swap-chain presenter for the framebuffer window

Goal: the game window becomes a normal D3D11 app with a real `IDXGISwapChain`, while
the guest-RAM readback and GDI path stay intact as the default.

Concrete shape:

* **New runtime source** (Windows-only), e.g.
  `refs/xboxrecomp/src/video/present_d3d11.cpp` (+ declarations in
  `video_player.h`). It owns the swap chain and a full-screen-triangle blit pipeline.
  Add it to `refs/xboxrecomp/src/video/CMakeLists.txt` under `if(WIN32)`, and link
  `d3d11 dxgi dxguid d3dcompiler`.
* **Reuse the existing native device** rather than creating a second one: export a
  getter from `nv2a_gpu_d3d11.cpp` (`extern "C" ID3D11Device *nv2a_gpu_device(void);`)
  and create the swap chain from the device's DXGI factory
  (`IDXGIDevice::GetAdapter` → `GetParent(IDXGIFactory)` → `CreateSwapChain`). This
  guarantees ReShade's factory/Present hooks see the same device the emulator renders
  with.
* **Window**: `fb_present.c` already owns `s_fb_hwnd`; hand that HWND to the
  presenter (`xbox_FramebufferWindowStart()` is the natural place, or add a
  `xbox_PresentInit(HWND)`). Keep the `fb_thread` message pump.
* **Per flip**: reuse the exact frame the window would show, `s_present[idx]` is the
  raw finished frame; `s_rgb` is the gamma-applied copy. Upload it to a dynamic
  `DXGI_FORMAT_B8G8R8A8_UNORM` texture and draw a full-screen triangle to the back
  buffer, then `IDXGISwapChain::Present(1, 0)`.
  * Present from the CPU buffer (not `Surface.texture`) in this phase: it is the
    finished, decoupled frame and avoids entangling the presenter with surface
    lifetime and `RECOMP_ASYNC_FLIP`.
  * Apply the guest gamma ramp in the shader (or keep `fb_gamma_apply` before upload)
    so brightness behaviour is unchanged.
  * Keep `StretchDIBits` as the default path; gate the new presenter on an env var
    (suggest `RECOMP_PRESENT=d3d11`, default `gdi`).
* **Wine/DXVK**: presenting from the native D3D11 device under Proton creates a
  Vulkan swap chain via DXVK and shows the window; that is the standard path.

Acceptance for Phase 1: with `RECOMP_PRESENT=d3d11`, the game window shows the same
picture as GDI at the same resolution and input/recording still work; logs are
error-clean. GDI remains default and unchanged.

### Phase 2, Inject stock ReShade

1. Fetch an official ReShade build (`ReShade64.dll` → rename to **`dxgi.dll`**) and
   place it next to `build/ghost.exe` in `recomp/game/`. Use the user's own
   `reshade-shaders` + a preset.
2. Add the override in `scripts/14-launch-recomp.sh` (and it propagates to
   `18-launch-user.sh`):
   ```bash
   export WINEDLLOVERRIDES="dxgi=n,b${WINEDLLOVERRIDES:+;$WINEDLLOVERRIDES}"
   ```
   If the `dxgi` form does not catch it, also try the `d3d11.dll` form
   (`d3dcompiler_47=n;dxgi=n,b` is the other documented combination).
3. Launch (`make launch`), press Home, confirm the overlay appears and a known effect
   visibly changes the image. Verify with the user (graphical result).

Risk on this phase is the ReShade↔DXVK proxy chain, not the emulator. If it fails,
fall through to Phase 4: A′ (explicit runtime via `create_effect_runtime`) first,
then B.

### Phase 3, Presets, config, and the user path

* Ship/point at a ReShade preset and shader paths that live outside the repo
  (copyright); document the exact `WINEDLLOVERRIDES` recipe in `AGENTS.md`/README.
* Wire `RECOMP_PRESENT=d3d11` into `scripts/18-launch-user.sh`'s passthrough knob
  list if we want the user path to present through D3D11 by default.
* Optional: allow an effect to be toggled without the overlay via the add-on API.

### Phase 4, Fallbacks (only if Phase 2 auto-hook fails)

**A′ first, explicit runtime, ReShade DLL still in play.** Set
`RESHADE_DISABLE_GRAPHICS_HOOK=1` for the proxy so ReShade stops auto-hooking, then
create/drive the runtime ourselves:

* If ReShade is loaded, our presenter (or a tiny add-on DLL that ReShade auto-loads)
  includes `include/reshade.hpp` (header-only) and calls
  `reshade::register_addon(GetModuleHandle(NULL))`, then on the first present
  `reshade::create_effect_runtime(reshade::api::device_api::d3d11, dev, ctx,
  swapchain, cfg, &rt)` and each frame `reshade::update_and_present_effect_runtime(rt)`.
* Alternative with no add-on DLL: build ReShade with a `BUILTIN_ADDON` that runs the
  same calls against the swap chain our presenter creates.
* This is deterministic and lets us scope effects to the gameplay window and leave
  FMVs/UI alone.

**B last, fully self-contained, no ReShade DLL.** Vendor ReShade FX
(`source/effect_*.*`) + the D3D11 API implementation under
`refs/xboxrecomp/third_party/reshade` (BSD-3; keep `LICENSE.md`), implement the
effect runtime against a minimal `reshade::api::swapchain` we own (or bind it to the
presenter's `IDXGISwapChain`), and run the chain on `Surface.texture` in
`nv2a_pb_exec.c` at `NV097_FLIP_STALL` **before** `nv2a_gpu_flip`'s readback. No DLL,
no Wine overrides, but no upstream overlay either, and we now own a large C++ tree.

---

## 6. Exact touch points

| File | Why |
|------|-----|
| `refs/xboxrecomp/src/video/fb_present.c` | owns the window (`s_fb_hwnd`), the frame double-buffer (`s_present[]`), gamma, and `fb_thread`; adds `xbox_FramebufferWindowSuspend`/`Size` (patched) |
| `refs/xboxrecomp/src/video/video_player.h` | declares `xbox_SetPresentHook` / `xbox_FramebufferWindowSuspend` / `xbox_FramebufferWindowSize` (patched) |
| `refs/xboxrecomp/src/kernel/nv2a_pb_exec.c` | `NV097_FLIP_STALL` (`:4311`) calls `nv2a_gpu_flip` → `xbox_FramebufferWindowPresent` → the hook; also defines `xbox_SetPresentHook` (patched) |
| `recomp/game/src/present_d3d11.cpp` | the opt-in D3D11/DXGI presenter (swap chain + `CopyResource` blit) |
| `recomp/game/CMakeLists.txt` | `GAME_SOURCES` includes `src/present_d3d11.cpp`; links `d3d11 dxgi dxguid` (already) |
| `recomp/game/src/main.c` | installs the presenter when `RECOMP_PRESENT=d3d11` (default GDI) |
| `scripts/18-launch-user.sh` | forwards `RECOMP_PRESENT` through the knob list |
| `scripts/14-launch-recomp.sh` | Phase 2: add `WINEDLLOVERRIDES="dxgi=n,b"` |
| `refs/xboxrecomp/src/kernel/nv2a_gpu_d3d11.cpp` | native D3D11 device (`:3306`), `nv2a_gpu_flip` (`:1692`), `stage_flip` (`:1660`), `Surface.texture`; **not** used by Phase 1 (presenter makes its own device); Phase 4 B injects here |

### 6.1 Where the code lives, in-repo vs the xboxrecomp fork

Question: can all of this live in **xbox-on-deb**, hooking/injecting into the already
built runtime, with no edits to `refs/xboxrecomp`?

Short answer: the **ReShade side, yes**; the **presenter can be forced in-repo, but
only via fragile in-process hooking**, because the runtime exposes no present seam and
the GDI blit cannot be switched off.

* **Tracked here (no fork change)**: `recomp/game/` (add sources to `GAME_SOURCES` in
  `recomp/game/CMakeLists.txt`), `scripts/`, `recomp/toolchain/`. The game project is
  linked into `ghost.exe` alongside the runtime static libs, so game-side code can
  reference runtime symbols, `nv2a_gpu_flip` (`nv2a_gpu.h:16`) and
  `xbox_FramebufferWindowPresent` (`video_player.h:76`) are non-static `extern "C"`,
  and can bring its own D3D11/DXGI code.
* **Getting a D3D present without editing the runtime**: compile a game-side module
  that installs an **inline detour** on the flip/present symbol, creates a DXGI
  swap chain on the runtime window (find it by class `XboxRecompFramebuffer`), uploads
  the captured frame and presents it; inject ReShade (`dxgi=n,b`) so it hooks that
  swap chain's `Present`. Physically all inside this repo.
  * **Catch 1, the GDI blit is always on.** `RECOMP_FB_WINDOW` is vestigial (only
    mentioned in comments); `xbox_FramebufferWindowStart()` runs unconditionally from
    `bridge_AvSetDisplayMode` (`kernel_bridge.c:1955`) and `fb_thread` calls
    `StretchDIBits` every new frame. With no env to disable it, the CPU blit fights the
    D3D present unless you *also* detour GDI (`StretchDIBits`/`BitBlt`), a second,
    uglier hook.
  * **Catch 2, brittleness.** Detours depend on runtime symbol addresses and
    prologues; a regen or runtime bump can break them without warning. The project's own
    rule is that runtime fixes go in the fork, not patches here (`README.md`,
    `AGENTS.md`).
* **The reliable seam is a few lines in the runtime**: expose a `g_present_hook`
  function pointer called from the `NV097_FLIP_STALL` path, or a
  `RECOMP_PRESENT=gdi|d3d11` switch. The presenter module itself still lives in
  `recomp/game/` (this repo); the toolkit only provides the call. That turns fragile
  detours into a supported hook.
* **Carried here as a pre-build patch (implemented).**
  `recomp/patches/0001-present-hook.patch` adds the `xbox_SetPresentHook()` seam
  plus `xbox_FramebufferWindowSuspend()` and `xbox_FramebufferWindowSize()` (see
  Appendix A). `scripts/25-apply-toolkit-patches.sh` applies/reverts the patch
  idempotently to `refs/xboxrecomp`, and `recomp/game/build.sh` runs it before
  every build, so `make build` always builds with it. `refs/` is gitignored, so
  the patch files under `recomp/patches/` are the tracked source of truth. This
  keeps the runtime change in this repo without a fragile in-process detour and
  without a fork commit, useful while prototyping. (Reverting:
  `bash scripts/25-apply-toolkit-patches.sh revert`; `make toolkit` (fast-forward)
  needs that first if it complains about local changes.)
* **ReShade itself is never "implemented in this repo"** unless its BSD-3 source is
  vendored (Route B). Otherwise it is a separate DLL injected via the Wine override in
  the launch scripts, and those scripts are already in-repo.

Recommendation: keep the presenter in `recomp/game/` and add the minimal present hook
to the fork. Treat an injection-only/detour-only build as a prototype, not shipping.

---

## 7. Constraints and risks

* **No swap chain today**, the whole point; Phase 1 is a prerequisite.
* **Readback is essential**, the guest reads its framebuffer; cloak/refraction
  samples the front buffer. Do not short-circuit `nv2a_gpu_flip`/publish.
* **Recording/replay, input, tests** depend on the `fb_present` window thread. The new
  presenter must not move or block the message pump or change focus behaviour; keep
  GDI as default.
* **ReShade + DXVK + Proton proxy chaining** is the main external risk (historically
  fragile; title-specific dxgi vs d3d11). Mitigation: Phase 4 A′ (explicit
  `create_effect_runtime`), then B.
* **Depth-dependent effects** (SSAO/RTGI/DOF) need a depth buffer; the presented
  frame is colour-only. Colour-space effects (grade, sharpen/CAS, bloom, LUT, FXAA)
  work; document the limitation. Wiring depth is a later optional step
  (`RECOMP_DEPTH_PUBLISH` exists but is off by default for this title).
* **Overlay input** (Home key) uses raw input; the window already uses `WM_INPUT`, so
  it should route, but verify, focus behaviour under Wine is idiosyncratic here
  (see the `SetForegroundWindow` comment at `fb_present.c:974`).
* **Performance**: DXVK present + ReShade is GPU work that did not exist; measure with
  `make ab-perf` and `[GPU] presentation:` FPS. The GDI path currently costs a full
  1920×1080 `StretchDIBits` per frame, so a GPU present may be a net win before
  ReShade.

---

## 8. Verification

Following `AGENTS.md`:

1. Every launch/test gets a diary entry in `recomp/diary/reshade.md` (command, result,
   error counts). After each run, grep the runtime log for the error-count tokens and
   record them; a run whose log is not error-free is not done.
2. Automated: `uv run python recomp/tests/run.py --attach --only ...` proves input,
   mission reach, audio and frame rate are unaffected by the presenter switch, and
   `--user-state --only a-mash` remains the "did we get further?" check.
3. `make ab-perf` for the FPS delta of `RECOMP_PRESENT=d3d11` vs `gdi`.
4. **Graphical result is verified by the user only** (per `AGENTS.md`): the reviewer
   launches `make launch`, opens the ReShade overlay, enables a known effect, and
   confirms it visibly applies to gameplay and that the game is otherwise unchanged.

---

## 9. Open questions

* Does ReShade's `dxgi` proxy chain cleanly to DXVK under `proton run` here, or is the
  `d3d11.dll` form required? (Test both; this decides A vs A′.)
* Present the CPU buffer or the zero-copy `Surface.texture`? Start CPU; revisit if
  ReShade needs colour-precision or performance.
* Should the DXGI presenter become the default once proven (GPU present is probably
  cheaper than GDI `StretchDIBits`), with GDI kept for tests?
* Ship a preset? Keep shaders/presets external (copyright), just document the paths.

---

## 10. Decision log

| Date | Decision | Why |
|------|----------|-----|
| 2026-10-15 | Do **not** attempt CPU-side effect reimplementation | Loses the ReShade FX ecosystem; not "ReShade" |
| 2026-10-15 | Reject a Vulkan present-time layer (vkBasalt/dlss-on-arc style) | Gameplay never reaches `vkQueuePresentKHR`; nothing to capture |
| 2026-10-15 | Phase 1 (DXGI presenter) ships opt-in, GDI stays default | Tests, recording/replay and input depend on today's window thread |
| 2026-10-15 | Prefer stock ReShade proxy (A) over embedding (B) | Far less code; keeps presets, overlay and add-ons upstream |
| 2026-10-15 | Keep the guest-RAM readback / publish path untouched | It is essential for the guest and for the cloak effect |
| 2026-10-15 | Carry the present-hook seam as a pre-build patch (`recomp/patches/`), not an in-process detour | Reproducible, tracked in this repo, and `make build` applies it; a detour is fragile |
| 2026-10-15 | Suspend the GDI blit (not just replace the flip call) when a hook is installed | Otherwise `fb_thread`'s no-flip path keeps `StretchDIBits`-ing live guest memory over the swap chain |
| 2026-10-15 | Presenter sizes from `xbox_FramebufferWindowSize`, not `GetClientRect` | The cross-thread HWND returned `0x0`/640x480 under Wine; `pitch` alone does not give the width |
| 2026-10-15 | No shaders in the presenter, one `CopyResource` | Converted pixels are `0x00RRGGBB` = `B8G8R8A8_UNORM` byte order; avoids a `d3dcompiler` dependency |

---

## 11. References

* ReShade source and FX compiler: github.com/crosire/reshade
  (`README.md`, `source/effect_*.cpp`, `source/dxgi/dxgi_swapchain.cpp`,
  `source/d3d11/d3d11.cpp`, `source/runtime.cpp`, `tools/fxc.cpp`).
* ReShade API / add-ons: <https://crosire.github.io/reshade-docs/>.
* Effect runtime flow: deepwiki.com/crosire/reshade/4.3-effect-runtime-flow.
* ReShade + Proton/DXVK: Proton issues
  [#4079](https://github.com/ValveSoftware/Proton/issues/4079),
  [#2908](https://github.com/ValveSoftware/Proton/issues/2908); DXVK issue
  [#1057](https://github.com/doitsujin/dxvk/issues/1057);
  `nesdeq/reshade` Linux installer.
* Prior art in-repo: `refs/dlss-on-arc` (Vulkan present-time layer, inapplicable
  here because gameplay never reaches `vkQueuePresentKHR`).
* Pipeline code: `refs/xboxrecomp/src/kernel/nv2a_gpu_d3d11.cpp`,
  `refs/xboxrecomp/src/kernel/nv2a_pb_exec.c`,
  `refs/xboxrecomp/src/video/fb_present.c`,
  `refs/xboxrecomp/src/d3d/d3d8_device.c`.

---

## Appendix A, Phase 1 implementation sketch

Concrete shape for the minimal, reliable split: a **hook pointer in the fork** and the
**presenter in this repo**. No fragile detours.

### A.1 Runtime seam (a few lines)

> Implemented and carried as `recomp/patches/0001-present-hook.patch`; applied
> pre-build by `scripts/25-apply-toolkit-patches.sh`. The snippets below are the
> patch contents.

`refs/xboxrecomp/src/video/video_player.h`:

```c
/* Called once per flip with the finished guest frame, when installed. The
 * presenter reads guest memory itself via xbox_GetMemoryOffset(). */
typedef void (*xbox_present_hook_t)(uint32_t fb_va, uint32_t pitch, void *user);
void xbox_SetPresentHook(xbox_present_hook_t hook, void *user);
```

`refs/xboxrecomp/src/kernel/nv2a_pb_exec.c`: include `../video/video_player.h`, define
`g_present_hook`/`g_present_user` and `xbox_SetPresentHook()` there (platform-neutral,
so the Linux toolkit build still links), and keep `xbox_FramebufferWindowPresent` as
the default (GDI) consumer. In the `NV097_FLIP_STALL` branch (around `:4277`) where it
already does:

```c
xbox_FramebufferWindowSet(dma_resolve(show), s_gpu.pitch);
xbox_FramebufferWindowPresent(dma_resolve(show), s_gpu.pitch);
```

become:

```c
if (g_present_hook) {
    g_present_hook(dma_resolve(show), s_gpu.pitch, g_present_user);
    /* still name the surface, so dumps/debug keep working */
    xbox_FramebufferWindowSet(dma_resolve(show), s_gpu.pitch);
} else {
    xbox_FramebufferWindowSet(dma_resolve(show), s_gpu.pitch);
    xbox_FramebufferWindowPresent(dma_resolve(show), s_gpu.pitch);
}
```

A hook does **not** stop the frame copy: the flip path still calls
`xbox_FramebufferWindowPresent` (so the window-title FPS counter and the F12
framebuffer dump keep working) and then calls the hook. What is stopped is the
window thread's blit, via two more small runtime entry points carried by the
same patch:

* `xbox_FramebufferWindowSuspend(int on)`, skips the GDI `StretchDIBits` while
  an external presenter owns `s_fb_hwnd` (message pumping, input,
  recording/replay, gamma refresh and the title all keep running).
  `xbox_SetPresentHook` sets it to `hook != NULL`.
* `xbox_FramebufferWindowSize(uint32_t *w, uint32_t *h)`, the title's render
  resolution. The presenter needs it because the window's client rect is not
  reliable from another thread under Wine (`GetClientRect` returned `0x0` in
  practice), and `pitch` alone does not give the width.

This is the whole runtime change. Gate it on `RECOMP_PRESENT=d3d11` in `main.c`
so GDI stays the default.

### A.2 Presenter (this repo, `recomp/game/src/present_d3d11.cpp`)

Implemented. Added to `GAME_SOURCES` in `recomp/game/CMakeLists.txt` (the
toolkit's MinGW `D3D11_FILTER_REDUCTION_TYPE_STANDARD`/`D3D11_MIP_LOD_BIAS_MAX`
defines already apply repo-wide, so the file needed no extra ones).

The shape is a little simpler than first sketched:

* `xbox_SetPresentHook(present_frame, NULL)` is installed from `main.c` when
  `RECOMP_PRESENT=d3d11` (before `mainCRTStartup_…`). All it does is register
  the callback and suspend GDI; there is no separate init call.
* The swap chain is created **lazily on the first flip**, inside the callback,
  once the window exists: `FindWindowA("XboxRecompFramebuffer", NULL)`, size
  from `xbox_FramebufferWindowSize`, then `D3D11CreateDeviceAndSwapChain`
  (B8G8R8A8_UNORM, 2 buffers, `DXGI_SWAP_EFFECT_DISCARD`). Runs on the guest
  (pushbuffer) thread; `fb_thread` keeps pumping messages.
* Per frame: host pointer = `xbox_GetMemoryOffset() + fb_va`; `Map` a dynamic
  B8G8R8A8 upload texture WRITE_DISCARD and convert the row (16/32 bpp + the
  guest gamma LUT, mirroring `fb_present.c`); `CopyResource` the whole texture
  to the back buffer; `Present(1, 0)`.
* **No shaders.** The converted pixel is `0x00RRGGBB` (byte order B,G,R,A),
  which is exactly `DXGI_FORMAT_B8G8R8A8_UNORM`, so one `CopyResource` is the
  whole draw and no `d3dcompiler` dependency is needed. DXGI scales the
  back buffer to the client area on present.

### A.3 ReShade

With the swap chain present, Phase 2 is unchanged: drop `ReShade64.dll` as
`recomp/game/build/dxgi.dll`, add `WINEDLLOVERRIDES="dxgi=n,b"` in
`scripts/14-launch-recomp.sh`, and ReShade auto-hooks the swap chain's `Present`. If
auto-hook misbehaves, switch to A′ (`RESHADE_DISABLE_GRAPHICS_HOOK=1` +
`reshade::create_effect_runtime` from the same presenter or a tiny add-on).

### A.4 Phase tracker

- [x] Phase 0: baseline diary `recomp/diary/reshade.md` (present-path recon was
      already done in §3).
- [x] Phase 1 (code): runtime seam (`xbox_SetPresentHook`,
      `xbox_FramebufferWindowSuspend`, `xbox_FramebufferWindowSize`) carried as
      `recomp/patches/0001-present-hook.patch` and applied pre-build by
      `scripts/25-apply-toolkit-patches.sh`; `RECOMP_PRESENT` gate +
      `recomp/game/src/present_d3d11.cpp` (on-first-flip swap chain + `CopyResource`
      blit). `recomp/game/build.sh` builds clean; a-mash passes on **both** the
      GDI default and `RECOMP_PRESENT=d3d11`, error-clean (`recomp/diary/reshade.md`).
- [x] Phase 1 (accept): **visual parity** of the d3d11 window vs GDI on the user
      path, user-verified 2026-10-15 (`RECOMP_PRESENT=d3d11 bash
      scripts/18-launch-user.sh`), see `recomp/diary/reshade.md`.
- [ ] Phase 2: ReShade `dxgi.dll` + `WINEDLLOVERRIDES="dxgi=n,b"`; overlay + one
      visible effect (user-verified).
- [ ] Phase 3: preset paths, user-path default, docs/AGENTS note.
- [ ] Phase 4 (only if needed): A′ explicit runtime, then B embed.