# 06 — Open questions, risks, and the next actions

## Open questions (need an answer before or during Phase 1)

1. **Is the finish-line the debug `Ghost.xbe` or a release-ish variant?**
   `Ghost.xbe` is a *Debug*-type XBE. It is the reference port's target
   (`0x001B3FBB`), so it is ours, but check whether `GhostR.xbe` (release?) boots
   more cleanly once the pipeline works. Keep `Ghost.xbe` as the canonical target
   until proven otherwise.

2. **How much of the D3D section does the game actually execute, vs. call
   through COM?**
   This decides the D3D fork. The fast way to learn it: once Phase 1 runs, log
   which D3D-section functions are reached. If the game drives raw NV2A
   pushbuffers, the HLE boundary is wrong and we must move toward register-level
   NV2A. Mitigation already in the toolkit (`xbox_nv2a` pushbuffer path).

3. **Does the game use `XeLoadSection`/demand-loaded XBE sections?**
   It imports `XeLoadSection`/`XeUnloadSection` (ordinals 327/328). If sections are
   demand-loaded, the recompiler must have all sections present and the loader
   must be handled, not stubbed. Check at runtime.

4. **MinGW vs MSVC for the generated C.**
   The toolkit is developed on MSVC. `recomp_types.h` uses MSVC-isms
   (`/bigobj`, `__declspec`, `RECOMP_TLS`). A MinGW cross-build is the plan; if it
   fights, build the executable in a Windows container and keep Linux for
   analysis and the runtime libraries.

5. **Which entry/global state does the CRT need pre-seeded?**
   The reference `main.c` leaves a TODO about `__active_heap`/CRT globals. Our
   source map names the CRT functions, so we can find the right globals instead
   of guessing.

6. **Bink FMV scope.** `Ghost.xbe` has a full BINK decoder linked in and ~90 MB
   of `.bik`/`.vid`. Do we decode Bink natively, or skip cutscenes for the first
   playable build? Default: skip for Phase 2, decode later.

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| MinGW build friction | medium | fallback to MSVC in a Windows container; analysis stays on Linux |
| D3D HLE fork wrong for this beta | medium | instrument D3D-section reachability; toolkit has register-level NV2A path |
| 1,193 unnamed functions hide the crash | medium | runtime ICALL feedback (Microsoft's feedback-loop idea) + `func_id` vtable groups; resolve iteratively |
| POSIX path silently taken | low | build target is explicitly `x86_64-w64-mingw32`; OpenGL backend not used |
| Generated code volume (millions of lines) | certain | `--split 250`, per-source-file chunks, `-O0`/`-O1` first, `/bigobj` or `-Wa,-mbig-obj` |
| Source map drifts from regeneration | low | `merge --apply` is a pipeline step; `.bak` kept; names come from data |

## Immediate next actions

1. **Rename pass.** Run `merge_names --names-json symbols/ghost.names.json --apply`
   on `functions.json`; confirm the recompiler emits `Class__method__VA` names.
2. **Project skeleton.** Copy `refs/xboxrecomp/templates/new-game` into
   `recomp/`; set `XBOXRECOCOMP_DIR` to `refs/xboxrecomp`; set entry
   `0x001B3FBB`; wire `config/fixups.toml`.
3. **First generation.** `tools.recomp --all --split 250` with
   `--exclude-manual`; record the unresolved-stub count as the Phase-1 baseline.
4. **First cross-build.** MinGW x64 → `Ghost.exe`; fix numeric-literal/section
   issues; produce a library-only build proof first.
5. **First Proton run.** Launch under GE-Proton with the `scghost` prefix; capture
   the crash and the first ICALL failure; start the one-crash-at-a-time loop.
6. **Write the post-processor** `annotate_gen.py` (source banner per function)
   and the per-source-file chunker, so readability is in place from the first
   generation rather than retrofitted.

## Deliberate simplifications (ponytail ledger)

- `demangled_to_c` is a lightweight MSVC demangler, not full. It yields
  `Class__method__VA`, good enough for readable C; full signatures live in the
  `demangled` field. Replace with a real demangler only if the noise matters.
- Source **line** numbers are not recovered (PDB has no line records). If needed,
  fingerprint-match `Star_d.pdb`. Not blocking.
- The kernel gap is one stub (`FscSetCacheSize`); no custom bridge work needed.
