#!/bin/bash
# Apply (or revert) the tracked hand-patches to the *generated* game code.
#
# scripts/20-regen-recomp.sh overwrites recomp/game/src/recomp/gen/* from the
# recompiler, taking every hand-edit with it. The patches under
# recomp/patches/gen/ are the tracked source of truth for those edits; this
# script puts them back. recomp/game/build.sh runs it before configuring, so a
# build is never made from a tree missing a fix.
#
#   bash scripts/26-apply-game-patches.sh           # apply (default)
#   bash scripts/26-apply-game-patches.sh revert    # undo
#   bash scripts/26-apply-game-patches.sh status    # what is applied where
#
# Each patch is a unified diff against the freshly generated file, with
# a/recomp/game/src/recomp/gen/<file> paths, applied from the repo root.
# Idempotent: an already-applied patch is detected by --reverse.
#
# If a patch no longer applies, the generator changed the surrounding code:
# regenerate the patch from the new tree rather than forcing it.
set -u

ROOT="${REPO_ROOT:-$HOME/WORKSPACE-VM/projects/xbox-on-deb}"
PATCHDIR="${PATCHDIR:-$ROOT/recomp/patches/gen}"
MODE="${1:-apply}"
ERR=/tmp/opencode/game-patch.err

shopt -s nullglob
patches=("$PATCHDIR"/*.patch)
if [ "${#patches[@]}" -eq 0 ]; then
    echo "no gen patches in $PATCHDIR"
    exit 0
fi

mkdir -p "$(dirname "$ERR")"
: >"$ERR"

failed=0
for p in "${patches[@]}"; do
    name="$(basename "$p")"
    if git -C "$ROOT" apply --check --reverse -p1 "$p" 2>>"$ERR"; then
        case "$MODE" in
            revert) git -C "$ROOT" apply --reverse -p1 "$p" 2>>"$ERR" \
                        && echo "reverted $name" ;;
            status) echo "applied: $name" ;;
            *)      echo "already applied: $name" ;;
        esac
    elif git -C "$ROOT" apply --check -p1 "$p" 2>>"$ERR"; then
        case "$MODE" in
            revert) echo "not applied: $name" ;;
            status) echo "not applied: $name" ;;
            *)      git -C "$ROOT" apply -p1 "$p" 2>>"$ERR" \
                        && echo "applied $name" ;;
        esac
    else
        echo "FAILED: $name does not apply cleanly (details in $ERR)" >&2
        failed=1
    fi
done

if [ "$failed" != "0" ]; then
    echo "gen patches do not match the generated tree; regenerate them" >&2
    exit 1
fi
