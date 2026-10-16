#!/bin/bash
# First-time setup: system-level dependencies + the recompilation toolkit.
#
#   bash scripts/00-init.sh        # or: make init
#
# Two steps:
#   1. system-level build packages (detected from /etc/os-release). This needs
#      root; when the package manager cannot run, the exact command is printed
#      to run by hand.
#   2. the recompilation toolkit, cloned (or fast-forwarded) into
#      refs/xboxrecomp from the Modded-Software fork over HTTPS.
#
# Then run `make install-deps` for the Python envs and the external bits
# (GE-Proton, game data).
set -eu

# Hardcoded: this sandbox resolves a script's own $0 through /proc, so
# dirname/readlink-based discovery lands in the wrong place (see build.sh).
ROOT="${REPO_ROOT:-$HOME/WORKSPACE-VM/projects/xbox-on-deb}"
XBOXRECOMP_REPO="${XBOXRECOMP_REPO:-https://github.com/Modded-Software/xboxrecomp.git}"

# Mirror the toolkit's own tools/linux/install_deps.sh: same dependencies,
# spelled per distro. These are for the native Linux build of the runtime
# libraries; the game itself is cross-compiled for Windows via zig.
detect_family() {
    local id id_like
    [ -r /etc/os-release ] || return 1
    id=$(. /etc/os-release && echo "${ID:-}")
    id_like=$(. /etc/os-release && echo "${ID_LIKE:-}")
    case " $id $id_like " in
        *" debian "*|*" ubuntu "*) echo debian ;;
        *" arch "*|*" archlinux "*) echo arch ;;
        *" fedora "*|*" rhel "*|*" centos "*) echo fedora ;;
        *) return 1 ;;
    esac
}

install_system_deps() {
    local family pkgs
    if ! family=$(detect_family); then
        echo "Could not identify the distro. Install by hand: a C toolchain, cmake,"
        echo "pkg-config, SDL2, OpenGL headers, libepoxy, OpenSSL and ffmpeg (dev)."
        return
    fi
    case "$family" in
        debian)
            pkgs=(build-essential cmake pkg-config libsdl2-dev libgl1-mesa-dev
                  libepoxy-dev libssl-dev libavcodec-dev libavformat-dev
                  libavutil-dev libswscale-dev) ;;
        arch)
            pkgs=(base-devel cmake pkgconf sdl2 mesa libepoxy openssl ffmpeg) ;;
        fedora)
            pkgs=(cmake gcc make pkgconf-pkg-config SDL2-devel mesa-libGL-devel
                  libepoxy-devel openssl-devel ffmpeg-devel) ;;
    esac

    if [ "$(id -u)" -eq 0 ]; then
        echo "installing ${#pkgs[@]} system packages ($family)..."
        case "$family" in
            debian) apt-get update && apt-get install -y "${pkgs[@]}" ;;
            arch)   pacman -S --needed --noconfirm "${pkgs[@]}" ;;
            fedora) dnf install -y "${pkgs[@]}" ;;
        esac
    else
        echo "system packages need root; run the one for this host ($family):"
        case "$family" in
            debian) echo "  sudo apt-get install -y ${pkgs[*]}" ;;
            arch)   echo "  sudo pacman -S --needed ${pkgs[*]}" ;;
            fedora) echo "  sudo dnf install -y ${pkgs[*]}" ;;
        esac
    fi
}

echo "== system-level dependencies =="
install_system_deps

echo "== recompilation toolkit -> refs/xboxrecomp =="
XBOXRECOMP_REPO="$XBOXRECOMP_REPO" bash "$ROOT/scripts/19-setup-toolkit.sh"

echo
echo "init done. Next: make install-deps (Python envs, GE-Proton, game data)."