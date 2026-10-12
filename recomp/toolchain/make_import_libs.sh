#!/bin/bash
# Regenerate the MinGW import libraries the toolkit links by their Windows SDK
# name but that zig's bundled mingw-w64 ships only as versioned .def files.
#
#   d3dcompiler -> zig knows d3dcompiler_47 only; SDK name resolves to
#                  D3DCOMPILER_47.dll.
#   xinput      -> zig knows xinput1_4 only; SDK name resolves to XINPUT1_4.dll
#                  on Windows 8+ (Wine/Proton provides it too).
#
# llvm-dlltool builds the import lib under the name upstream asks for, and the
# compiler wrappers put toolchain/lib on the link search path. Run after
# changing ziglang versions.
set -e
ROOT=/home/agent/WORKSPACE-VM/projects/xbox-on-deb
ZIGLIB="$ROOT/.venv-recomp/lib/python3.13/site-packages/ziglang/lib/libc/mingw/lib-common"
OUT="$ROOT/recomp/toolchain/lib"
mkdir -p "$OUT"
llvm-dlltool -m i386:x86-64 -d "$ZIGLIB/d3dcompiler_47.def" -l "$OUT/libd3dcompiler.a"
llvm-dlltool -m i386:x86-64 -d "$ZIGLIB/xinput1_4.def"    -l "$OUT/libxinput.a"
echo "wrote $OUT/libd3dcompiler.a $OUT/libxinput.a"
