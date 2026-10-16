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
#
# Idempotent: safe to re-run. On an existing checkout it fast-forwards the
# *checked-out* branch from its own upstream (not a hardcoded main), and leaves
# a repository that is mid-merge/rebase/cherry-pick alone rather than getting in
# the way of an operator's in-flight work.
set -eu

# Hardcoded: this sandbox resolves a script's own $0 through /proc, so
# dirname/readlink-based discovery lands in the wrong place (see build.sh).
ROOT="${REPO_ROOT:-$HOME/WORKSPACE-VM/projects/xbox-on-deb}"
DEST="$ROOT/refs/xboxrecomp"
REPO="${XBOXRECOMP_REPO:-git@github.com:Modded-Software/xboxrecomp.git}"

mkdir -p "$ROOT/refs"

# The ref to fast-forward from: the checked-out branch's configured upstream,
# else origin/<branch>, else origin/main (the fork's default). Hardcoding
# origin/main breaks whenever the checkout is on any other branch.
update_ref() {
    local branch up
    branch=$(git -C "$DEST" rev-parse --abbrev-ref HEAD)
    up=$(git -C "$DEST" for-each-ref --format='%(upstream:short)' "refs/heads/$branch")
    if [ -n "$up" ]; then
        echo "$up"
    elif _sha=$(git -C "$DEST" show-ref --verify "refs/remotes/origin/$branch"); then
        echo "origin/$branch"
    else
        echo origin/main
    fi
}

if [ ! -d "$DEST/.git" ]; then
    echo "cloning $REPO -> $DEST"
    if ! git clone "$REPO" "$DEST"; then
        echo "clone failed; check access to $REPO" >&2
        exit 1
    fi
else
    GITDIR=$(git -C "$DEST" rev-parse --absolute-git-dir)
    if [ -e "$GITDIR/MERGE_HEAD" ] || [ -e "$GITDIR/CHERRY_PICK_HEAD" ] \
        || [ -e "$GITDIR/REVERT_HEAD" ] || [ -e "$GITDIR/rebase-merge" ] \
        || [ -e "$GITDIR/rebase-apply" ]; then
        echo "refs/xboxrecomp has a git operation in progress; not updating."
        echo "Finish or abort it (git -C $DEST merge --abort, etc.), then re-run."
        exit 0
    fi

    echo "updating $DEST from origin"
    if ! git -C "$DEST" fetch origin; then
        echo "fetch failed; check access to $REPO" >&2
        exit 1
    fi
    REF=$(update_ref)
    echo "fast-forwarding $REF"
    if ! git -C "$DEST" merge --ff-only "$REF"; then
        echo "refs/xboxrecomp has local commits; not a fast-forward." >&2
        echo "Move them onto the fork or reset by hand." >&2
        exit 1
    fi
fi

echo "toolkit: $(git -C "$DEST" rev-parse --short HEAD) $(git -C "$DEST" log -1 --format=%s)"
