# Toolkit patches

This directory carries **no** patches. The present hook, the D3D11 GPU device
split and the depth no-stale-refresh change used to live here as `*.patch` files
applied to `refs/xboxrecomp` before every build; they are now commits on the
toolkit fork (`scripts/19-setup-toolkit.sh`, branch `aknavj-rebased`). Runtime
changes belong there, not here.

`build.sh` no longer applies anything from this directory.

If a patch must ever be carried in *this* repo, it may only be guest (game) code
under `recomp/game/`; the apply helper is
`scripts/25-apply-toolkit-patches.sh` (a no-op while this directory has no
`*.patch`). See `AGENTS.md` for the fork-first rule.