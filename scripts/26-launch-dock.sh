#!/bin/bash
# GNOME dock launch entries for the recompiled game.
#
#   bash scripts/26-launch-dock.sh default         # GDI present, 512 shadow maps
#   bash scripts/26-launch-dock.sh reshade         # + ReShade (RECOMP_PRESENT=d3d11)
#   bash scripts/26-launch-dock.sh record          # default + window/audio recording
#   bash scripts/26-launch-dock.sh reshade-record  # reshade + recording
#
# Every mode records all input edges unconditionally: SESSION is always set to a
# fresh timestamped id and RECORD defaults on in scripts/18-launch-user.sh, so a
# recording is written to pfx/drive_c/recomp-record-<SESSION>.txt on every run.
#
# Shadow-map texture size is pinned to 512 (the toolkit's own default) so every
# entry is explicit about it. RECOMP_PRESENT=d3d11 gives the game window a
# D3D11/DXGI swap chain for ReShade to hook; scripts/14-launch-recomp.sh picks
# up build/dxgi.dll automatically. Stop a recording with: make stop-video
set -u
ROOT="${REPO_ROOT:-$HOME/WORKSPACE-VM/projects/xbox-on-deb}"
cd "$ROOT"

MODE="${1:-default}"
case "$MODE" in
    default|reshade|record|reshade-record) ;;
    *) echo "usage: $0 default|reshade|record|reshade-record" >&2; exit 2 ;;
esac

# 512 shadow-map texture (the title's hardware shadow maps).
export SCGHOST_SHADOW_TEX="${SCGHOST_SHADOW_TEX:-512}"

# Input recording, unconditionally, fresh session per launch. REPLAY=0 forces
# the record branch even if the environment happens to set REPLAY=1.
export SESSION="dock-$(date +%Y%m%d-%H%M%S)"
export RECORD=1
export REPLAY=0

# ReShade needs the D3D11/DXGI presenter; the rest keep the default GDI blit.
case "$MODE" in
    reshade|reshade-record) export RECOMP_PRESENT=d3d11 ;;
    *) export RECOMP_PRESENT=gdi ;;
esac

bash scripts/18-launch-user.sh

# Recording: wait for the window, then capture the Wine window + ghost.exe audio.
case "$MODE" in
    record|reshade-record) bash scripts/23-record-video.sh start "$SESSION" ;;
esac