# Toolkit patches

Unified diffs applied to `refs/xboxrecomp` (the xboxrecomp toolkit checkout) by
`scripts/25-apply-toolkit-patches.sh`, which `recomp/game/build.sh` runs before every
build. `refs/` is gitignored, so these files are the tracked source of truth for the
change.

Normal workflow is still to commit runtime work to the toolkit fork
(`scripts/19-setup-toolkit.sh`), see `AGENTS.md`. Use a patch here only when a change
must be carried in this repo and applied pre-build.

## Files

| Patch | What it adds |
|-------|--------------|
| `0001-present-hook.patch` | An optional per-flip present callback (`xbox_SetPresentHook`) plus two window controls the alternative presenter needs: `xbox_FramebufferWindowSuspend` (stop the GDI blit while the hook owns the window) and `xbox_FramebufferWindowSize` (the title's render resolution, for swap-chain sizing). Lets a D3D11/DXGI presenter (e.g. for ReShade) take over from the built-in GDI framebuffer window. See `docs/07-reshade-integration.md` Appendix A. |

## Commands

```sh
bash scripts/25-apply-toolkit-patches.sh          # apply (idempotent)
bash scripts/25-apply-toolkit-patches.sh revert   # undo
```

Ordering: `make toolkit` (fast-forward) first, then build. If `make toolkit` refuses
because of local changes, `revert` the patches first.

## Adding a patch

1. Edit files under `refs/xboxrecomp`.
2. `git -C refs/xboxrecomp diff -- <files> > recomp/patches/000N-name.patch`
   (name only the files you changed, since the checkout may have unrelated local edits).
3. Revert those files in `refs/` if you want the patch to be the only copy.
4. Run the apply script to confirm it applies cleanly.