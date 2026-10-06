#!/bin/bash
set -euo pipefail

REPO_ROOT="$(pwd)"
if [ ! -d "$REPO_ROOT/site" ] || [ ! -f "$REPO_ROOT/tools/serve.mjs" ]; then
    echo "serve: must run from the wiki root (the directory containing site/)" >&2
    exit 1
fi

PORT="${PORT:-18082}" exec node tools/serve.mjs
