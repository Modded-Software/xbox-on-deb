#!/bin/bash
# Clone or fast-forward the xboxrecomp toolkit fork into refs/xboxrecomp.
#
#   bash scripts/19-setup-toolkit.sh
#
# The toolkit is its own repository (Modded-Software/xboxrecomp, a fork of
# sp00nznet/xboxrecomp). This project does not carry patches against it any
# more: the StarCraft: Ghost runtime work lives as commits on that fork's
# main, so getting the toolkit is just a clone or a fast-forward.
#
# Override the remote with XBOXRECOMP_REPO=... if you use your own fork.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/refs/xboxrecomp"
REPO="${XBOXRECOMP_REPO:-git@github.com:Modded-Software/xboxrecomp.git}"

mkdir -p "$ROOT/refs"

if [ ! -d "$DEST/.git" ]; then
    echo "cloning $REPO -> $DEST"
    if ! git clone "$REPO" "$DEST"; then
        echo "clone failed; check access to $REPO" >&2
        exit 1
    fi
else
    echo "updating $DEST from origin"
    if ! git -C "$DEST" fetch origin; then
        echo "fetch failed; check access to $REPO" >&2
        exit 1
    fi
    if ! git -C "$DEST" merge --ff-only origin/main; then
        echo "refs/xboxrecomp has local commits; not a fast-forward." >&2
        echo "Move them onto the fork or reset by hand." >&2
        exit 1
    fi
fi

echo "toolkit: $(git -C "$DEST" rev-parse --short HEAD) $(git -C "$DEST" log -1 --format=%s)"
