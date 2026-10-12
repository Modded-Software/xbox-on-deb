# Cross-compile the recompiled game for Windows x86_64 using the ziglang PyPI
# package as the toolchain (clang + lld + mingw-w64 sysroot bundled). This is
# the no-root alternative to a system gcc-mingw-w64 install.
#
#   cmake -S recomp/game -B recomp/game/build \
#         -DCMAKE_TOOLCHAIN_FILE=recomp/toolchain/zig-windows-x64.cmake
#
# The wrappers in bin/ pin the target triple; nothing else is needed, because
# zig carries its own sysroot (so we deliberately do NOT set
# CMAKE_FIND_ROOT_PATH -- there is no /usr/x86_64-w64-mingw32 to point at).

set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_SYSTEM_PROCESSOR x86_64)

set(CMAKE_C_COMPILER   "${CMAKE_CURRENT_LIST_DIR}/bin/x86_64-w64-mingw32-gcc")
set(CMAKE_CXX_COMPILER "${CMAKE_CURRENT_LIST_DIR}/bin/x86_64-w64-mingw32-g++")
set(CMAKE_AR           "${CMAKE_CURRENT_LIST_DIR}/bin/x86_64-w64-mingw32-ar")
set(CMAKE_RANLIB       "${CMAKE_CURRENT_LIST_DIR}/bin/x86_64-w64-mingw32-ranlib")

# Find host programs (cmake, python) on the host, not in a target root.
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE NEVER)
