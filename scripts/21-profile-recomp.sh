#!/bin/bash
# Profile the recompiled game in real in-mission gameplay.
#
# Drives the game to the first mission with the canonical A-mash (the same
# path as `run.py --user-state --only a-mash`), perf-records all ghost.exe
# threads, then symbolicates the samples back to lifted guest functions
# (Wine maps the PE anonymously, so plain perf shows everything as [JIT]).
#
# Usage:
#   scripts/21-profile-recomp.sh                 # 30s sample, user launcher
#   scripts/21-profile-recomp.sh --secs 60
#   scripts/21-profile-recomp.sh --symbolize-only --perf /tmp/opencode/perf.data
#
# Output: the perf.data (--perf, default /tmp/opencode/perf-recomp.data) and a
# sibling .report.txt grouped by lifted function and source file.
set -uo pipefail

ROOT=/home/agent/WORKSPACE-VM/projects/xbox-on-deb
cd "$ROOT"

# The stock /usr/bin/perf wrapper insists on an exact kernel match; the
# linux-tools binary for the running kernel is symlinked here.
export PATH="$HOME/.local/bin:$PATH"

exec python3 scripts/profile-recomp.py "$@"