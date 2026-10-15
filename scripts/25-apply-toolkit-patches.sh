#!/bin/bash
# Apply (or revert) the patch set this project carries against refs/xboxrecomp.
#
# Runtime changes normally live as commits on the toolkit fork (see
# scripts/19-setup-toolkit.sh). This is the alternative for a change that must be
# carried *here* instead: drop a unified diff into recomp/patches/ and it is
# applied to refs/xboxrecomp idempotently. recomp/game/build.sh runs this before
# every build, so `make build` always builds with the patches applied.
#
#   bash scripts/25-apply-toolkit-patches.sh          # apply (default)
#   bash scripts/25-apply-toolkit-patches.sh revert   # undo
#   PATCHDIR=... bash scripts/25-apply-toolkit-patches.sh
#
# Ordering: run this AFTER `make toolkit` (a fast-forward merge) and BEFORE
# `make build`. If `make toolkit` complains about local changes, revert first.
#
# Note: `refs/` is gitignored in this repo; the patch files under recomp/patches/
# are the tracked source of truth.
set -eu

ROOT="${REPO_ROOT:-$HOME/WORKSPACE-VM/projects/xbox-on-deb}"
DEST="$ROOT/refs/xboxrecomp"
PATCHDIR="${PATCHDIR:-$ROOT/recomp/patches}"
MODE="${1:-apply}"
ERR="/tmp/opencode/toolkit-patch.err"

if [ ! -d "$DEST/.git" ]; then
    echo "refs/xboxrecomp is not a git checkout; run 'make toolkit' first" >&2
    exit 1
fi

shopt -s nullglob
patches=("$PATCHDIR"/*.patch)
if [ "${#patches[@]}" -eq 0 ]; then
    echo "no toolkit patches in $PATCHDIR"
    exit 0
fi

mkdir -p "$(dirname "$ERR")"
: >"$ERR"

for p in "${patches[@]}"; do
    name="$(basename "$p")"
    if git -C "$DEST" apply --check --reverse "$p" 2>>"$ERR"; then
        # Already applied.
        if [ "$MODE" = revert ]; then
            git -C "$DEST" apply --reverse "$p" 2>>"$ERR"
            echo "reverted $name"
        else
            echo "already applied: $name"
        fi
    elif git -C "$DEST" apply --check "$p" 2>>"$ERR"; then
        if [ "$MODE" = revert ]; then
            echo "not applied: $name"
        else
            git -C "$DEST" apply "$p" 2>>"$ERR"
            echo "applied $name"
        fi
    else
        echo "FAILED: $name does not apply cleanly (details in $ERR)" >&2
        exit 1
    fi
done