#!/bin/bash
# Apply recomp/patches/*.patch to an xboxrecomp clone.
#
#   bash recomp/patches/apply.sh [path-to-xboxrecomp]
#
# Defaults to refs/xboxrecomp under the repo root.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
TARGET="${1:-$HERE/../../refs/xboxrecomp}"

for p in "$HERE"/*.patch; do
    echo "applying $(basename "$p") to $TARGET"
    git -C "$TARGET" apply --whitespace=nowarn "$p"
done
echo "done"
