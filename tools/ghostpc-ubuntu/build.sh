#!/bin/bash
# Cross-build GhostPC (i686 Windows) on Ubuntu with the repo's zig toolchain.
#
#   bash tools/ghostpc-ubuntu/build.sh          # build
#   JOBS=4 bash tools/ghostpc-ubuntu/build.sh   # parallel compile
#
# Sources are copied to build/src; the tracked patches under patches/ are
# applied there, so refs/GhostPC is never modified.
set -euo pipefail

ROOT="${REPO_ROOT:-$HOME/WORKSPACE-VM/projects/xbox-on-deb}"
HERE="$ROOT/tools/ghostpc-ubuntu"
SRC="$ROOT/refs/GhostPC"
BUILD="$HERE/build"
JOBS="${JOBS:-$(nproc)}"
CXX="$ROOT/recomp/toolchain/bin/i686-w64-mingw32-g++"

if [ ! -d "$SRC/src" ]; then
    echo "error: $SRC/src not found; clone https://github.com/Tamamo-no-Bae/GhostPC into refs/GhostPC" >&2
    exit 1
fi
if [ ! -x "$CXX" ]; then
    echo "error: $CXX not found (run scripts/19-setup-toolkit.sh or recomp/toolchain setup)" >&2
    exit 1
fi

# zig's bundled mingw sysroot (version-independent: first python3* match).
ZIGROOT=""
for d in "$ROOT"/.venv-recomp/lib/python*/site-packages/ziglang; do
    if [ -d "$d/lib/libc/mingw/lib32" ]; then ZIGROOT="$d"; break; fi
done
if [ -z "$ZIGROOT" ]; then
    echo "error: ziglang not found in .venv-recomp; run uv sync or scripts/19-setup-toolkit.sh" >&2
    exit 1
fi
MINGW="$ZIGROOT/lib/libc/mingw"

rm -rf "$BUILD/src"
mkdir -p "$BUILD/src" "$BUILD/obj" "$BUILD/lib" "$BUILD/logs"
cp "$SRC"/src/*.cpp "$SRC"/src/*.h "$BUILD/src/"
cp "$HERE"/compat/*.h "$HERE"/compat/*.cpp "$BUILD/src/"

for p in "$HERE"/patches/*.patch; do
    echo "applying $(basename "$p")"
    patch -p2 -d "$BUILD/src" < "$p"
done

# Import libraries: zig ships .def files but not the SDK-named .a files the
# upstream pragmas ask for, and its cached kernel32.lib is XP-baseline (no
# SRW/InitOnce/Fls). Build a complete set from the same .def files.
if ! have_dlltool=$(command -v llvm-dlltool); then
    have_dlltool=""
fi
if [ -z "$have_dlltool" ]; then
    echo "error: llvm-dlltool not found (apt install llvm)" >&2
    exit 1
fi
mkdir -p "$BUILD/defs"
gen_import() {
    n="$1"
    if [ -f "$MINGW/lib-common/$n.def.in" ]; then
        # The first line includes zig's per-arch template; the rest is a
        # complete, undecorated export list (what zig's own .lib uses).
        sed '1d' "$MINGW/lib-common/$n.def.in" > "$BUILD/defs/$n.def"
    elif [ -f "$MINGW/lib-common/$n.def" ]; then
        cp "$MINGW/lib-common/$n.def" "$BUILD/defs/$n.def"
    else
        # lib32 carries decorated stdcall names; Windows/Wine export the
        # kernel32-style DLLs undecorated, so strip the @N suffix.
        sed 's/@[0-9][0-9]*$//' "$MINGW/lib32/$n.def" > "$BUILD/defs/$n.def"
    fi
    llvm-dlltool -m i386 -d "$BUILD/defs/$n.def" -l "$BUILD/lib/lib$n.a"
}
for n in kernel32 user32 gdi32 shell32 ole32 winmm dbghelp d3d9 xinput9_1_0 d3dcompiler_47 comctl32 ws2_32; do
    gen_import "$n"
done

FLAGS="-std=c++17 -O2 -fms-extensions -fasm-blocks -fpermissive \
-include ghostpc_ubuntu_compat.h -D_CRT_SECURE_NO_WARNINGS -DNOMINMAX \
-DWIN32_LEAN_AND_MEAN -I."

compile_one() {
    local f="$1"
    if ! "$CXX" $FLAGS -c "$f" -o "$BUILD/obj/$(basename "${f%.cpp}").o"; then
        echo "COMPILE_FAIL $f" >&2
        return 1
    fi
}
export -f compile_one
export CXX FLAGS BUILD

cd "$BUILD/src"
fail=0
for f in *.cpp; do
    while [ "$(jobs -rp | wc -l)" -ge "$JOBS" ]; do wait -n || fail=1; done
    compile_one "$f" &
done
while [ "$(jobs -rp | wc -l)" -gt 0 ]; do wait -n || fail=1; done
if [ "$fail" != 0 ]; then
    echo "error: compilation failed" >&2
    exit 1
fi

"$CXX" -mwindows -Wl,--image-base,0x10000000 -o "$BUILD/GhostPC.exe" "$BUILD"/obj/*.o \
    -L"$BUILD/lib" "$BUILD/lib/libkernel32.a" \
    -ld3d9 -lxinput9_1_0 -lws2_32 -lcomctl32 -ld3dcompiler_47 -ldbghelp \
    -luser32 -lgdi32 -lshell32 -lole32 -lwinmm

PY="$ROOT/.venv-recomp/bin/python"
if [ ! -x "$PY" ]; then PY=python3; fi
"$PY" "$HERE/patch-pe.py" "$BUILD/GhostPC.exe"

echo "built $BUILD/GhostPC.exe"
