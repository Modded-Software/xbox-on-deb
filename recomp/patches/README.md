# Game-code patches

Patches here change **guest (game) code** in `recomp/game/`. Runtime changes are
commits on the toolkit fork (`refs/xboxrecomp`), never patches.

The generated tree `recomp/game/src/recomp/gen/` is rewritten by
`scripts/20-regen-recomp.sh`, so a hand-edit there survives only until the next
regen. `gen/` holds those edits as tracked unified diffs; they are the source of
truth and the only copy that is in git.

```
gen/0001-shadow-tex-size.patch    shadow-map resolution knob
gen/0002-kbm-no-autoyaw.patch     KBM direct look: ShouldAutoYaw returns 0
```

## Use

```bash
bash scripts/26-apply-game-patches.sh           # apply (default), idempotent
bash scripts/26-apply-game-patches.sh revert    # undo
bash scripts/26-apply-game-patches.sh status    # applied / not applied per file
```

`recomp/game/build.sh` runs `apply` before configuring (and before the profiled
copy is made), so a build is never made from a tree missing a fix. A patch that
no longer applies stops the build and names the file -- the generator changed the
surrounding code, so regenerate the patch from the new tree instead of forcing it.

## Format

A unified diff against the freshly generated file, applied from the repo root:

```
diff --git a/recomp/game/src/recomp/gen/recomp_0006.c b/recomp/game/src/recomp/gen/recomp_0006.c
--- a/recomp/game/src/recomp/gen/recomp_0006.c
+++ b/recomp/game/src/recomp/gen/recomp_0006.c
```

Each edit is marked in the C with `/* MANUAL PATCH ... */`, so
`rg 'MANUAL PATCH' recomp/game/src/recomp/gen` shows exactly which fixes are
present. Prose above the diff explains symptom, cause and verification; see
`recomp/game/MANUAL_PATCHES.md` for the ledger.

## Regenerating a patch

1. Keep a copy of the freshly generated file.
2. Re-apply the edit by hand.
3. `diff -u fresh current > new.patch`, then rewrite the two `---`/`+++` lines to
   the `a/`…`b/` paths above.
4. `git apply --check -p1 new.patch` against the fresh tree.
