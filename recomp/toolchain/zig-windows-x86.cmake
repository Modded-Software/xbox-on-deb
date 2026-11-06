# Cross-compile the Win32 installer for 32-bit Windows (i686), so it runs on
# 32-bit Windows XP. The game itself (recomp/game) stays x86_64; only the setup
# program and the uninstaller are built with this toolchain.
#
#   cmake -S recomp/installer -B recomp/installer/build-x86 \
#         -DCMAKE_TOOLCHAIN_FILE=recomp/toolchain/zig-windows-x86.cmake

set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_SYSTEM_PROCESSOR i686)

set(CMAKE_C_COMPILER   "${CMAKE_CURRENT_LIST_DIR}/bin/i686-w64-mingw32-gcc")
set(CMAKE_CXX_COMPILER "${CMAKE_CURRENT_LIST_DIR}/bin/i686-w64-mingw32-g++")
set(CMAKE_AR           "${CMAKE_CURRENT_LIST_DIR}/bin/i686-w64-mingw32-ar")
set(CMAKE_RANLIB       "${CMAKE_CURRENT_LIST_DIR}/bin/i686-w64-mingw32-ranlib")
set(CMAKE_RC_COMPILER  "${CMAKE_CURRENT_LIST_DIR}/bin/i686-w64-mingw32-rc")

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE NEVER)
