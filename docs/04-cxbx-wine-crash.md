# 04 — Cxbx-Reloaded under Wine: init crash and workaround

This documents the black-screen / crash-dialog problem when running the Xbox
release build (`Ghost.xbe`) under Cxbx-Reloaded on Wine, and the two changes
that make it boot.

## Symptom

`cxbx.exe <Ghost.xbe>` (Cxbx CI-585c49a, run via GE-Proton11-1) either

- opens its GUI and then closes with no render window, or
- shows a crash MessageBox
  `The running xbe has encountered an unhandled exception (Code := 0xC0000005)`
  with Abort/Retry/Ignore.

## Diagnosis

Enable the kernel log (`[core] KrnlDebugMode = 0x2`, `LogLevel = 3`; Cxbx
rewrites `settings.ini` on exit, so set it immediately before launching).
`logs/KrnlDebug.txt` always ends the same way:

```
[0x....] DEBUG: INIT    Determining CPU affinity.
[0x....] MAIN: Received Exception (Code := 0xC0000005)
 EIP := 0x??????08(=cxbxr-emu.dll+0x399208)
 ...
 AV : WRITE from/to address 0xF8??????2      <- random high 32-bit address
 EIP is OUTSIDE Xbox code range
```

- Crash offset `cxbxr-emu.dll+0x399208` is constant; the *faulting address*
  varies every run.
- It happens right after the affinity step, i.e. in Cxbx's CPU-affinity
  policy init, before the XBE runs.
- Reproduced under GE-Proton11-1 (Wine 11 staging) **and** GE-Proton7-55
  (Wine 7.0 staging), and under system Wine 9.0. `UseAllCores = true`
  (which should bypass the affinity code) did not help.

The Windows-10 affinity policy path calls `GetSystemCpuSetInformation`, which
is a weak/incorrect stub in Wine; Cxbx then walks bogus pointers and writes to
a garbage address.

A side lead: installing `vcrun2019` via winetricks (which the Cxbx docs
suggest) set native `msvcp140`/`vcruntime140` overrides and moved the crash
*into* `msvcp140`. `winetricks alldlls=default` restores the Wine builtins and
removes that secondary failure. The Cxbx build runs fine on Wine's built-in
runtimes here.

## Fix

1. **Set the prefix's Windows version to Windows 7.** This makes Cxbx select
   the Win7 affinity policy (`GetProcessAffinityMask`,
   `SetThreadAffinityMask`), avoiding the broken `GetSystemCpuSetInformation`
   path:
   ```
   WINEPREFIX=~/Games/scghost-prefix/pfx wine reg add \
       "HKCU\\Software\\Wine" /v Version /d win7 /f
   ```
2. **Retry from a clean emulated-media state.** Even with the version fix the
   first launch or two still die during init; a retry usually reaches
   `ResetSwapChain`. `scripts/06-retry-launch.sh` automates this:
   ```
   bash scripts/06-retry-launch.sh "extracted/StarCraft Ghost Xbox Finn Hillbilly/Ghost.xbe"
   ```
   Success is detected by `D3D9DeviceEx::ResetSwapChain` appearing in the run
   log — the moment the 640x480 render window is created. Observed success
   rate: 1 in 3 attempts (attempt 3 above).

When it succeeds, `xwininfo -root -tree` shows the emulator render window
`640x480+0+0` (owned by the Wineserver, no name) and `cxbxr-ldr.exe` stays
alive. The build then plays the intro/splash, then sits on a black frame —
the same state as the first ever successful boot.

## Notes

- The DXVK render window cannot be captured with `xwd`/`XGetImage`
  (`BadMatch`); it must be observed on-screen.
- `wineserver -k` kills *every* process in the prefix, including a running
  emulator. To clean up stale GUI processes without disturbing a live run,
  kill individual PIDs instead.
- Cxbx rewrites `settings.ini` on exit, so debug-log settings do not persist.
