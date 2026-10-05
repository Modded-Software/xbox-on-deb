#!/bin/bash
set -euo pipefail
# Capture the whole screen via GNOME Shell's D-Bus screenshot API.
# Usage: screenshot.sh [output.png]
OUT="${1:-/tmp/opencode/screenshot.png}"
gdbus call --session \
    --dest org.gnome.Shell.Screenshot \
    --object-path /org/gnome/Shell/Screenshot \
    --method org.gnome.Shell.Screenshot.Screenshot true false "$OUT"
ls -la "$OUT"
