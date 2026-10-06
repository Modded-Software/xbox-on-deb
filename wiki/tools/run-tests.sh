#!/bin/bash
set -euo pipefail

REPO_ROOT="$(pwd)"
if [ ! -d "$REPO_ROOT/site" ] || [ ! -d "$REPO_ROOT/tools" ]; then
    echo "run-tests: must run from the wiki root (the directory containing site/)" >&2
    exit 1
fi

node tools/measure.mjs --check
node --test 'tools/test-*.mjs'
