#!/bin/bash
# Wait for the game window to map, then give it keyboard focus.
# Run in the background by 18-launch-user.sh; see scripts/focus-game.py.
set -u
ROOT="${REPO_ROOT:-$HOME/WORKSPACE-VM/projects/xbox-on-deb}"
cd "$ROOT" || exit 1
for _ in $(seq 1 120); do
    if "$ROOT/.venv-recomp/bin/python" "$ROOT/scripts/focus-game.py"; then
        exit 0
    fi
    sleep 0.5
done
exit 1
