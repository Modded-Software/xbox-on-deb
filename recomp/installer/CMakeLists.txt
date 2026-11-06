cmake_minimum_required(VERSION 3.20)
project(sghost_setup C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_compile_definitions(WIN32_LEAN_AND_MEAN NOMINMAX UNICODE _UNICODE)

# The Ghost icon (generated from the archive key art by tools/make_icon.py).
set(GHOST_ICON "${GHOST_ASSET_DIR}/ghost.ico")
set(GHOST_ICON_RESOURCE "")
if(EXISTS "${GHOST_ICON}")
    file(TO_CMAKE_PATH "${GHOST_ICON}" GHOST_ICON)
    set(GHOST_ICON_RESOURCE "1 ICON \"${GHOST_ICON}\"")
endif()
configure_file(resource.rc.in "${CMAKE_CURRENT_BINARY_DIR}/resource.rc" @ONLY)

add_executable(StarCraftGhostSetup WIN32 src/setup.cpp "${CMAKE_CURRENT_BINARY_DIR}/resource.rc")
target_link_libraries(StarCraftGhostSetup PRIVATE
    gdiplus winmm shell32 shlwapi ole32 uuid advapi32 comdlg32 user32 gdi32)

add_executable(GhostRecompUninstall WIN32 src/uninstall.cpp "${CMAKE_CURRENT_BINARY_DIR}/resource.rc")
target_link_libraries(GhostRecompUninstall PRIVATE
    shell32 ole32 advapi32 user32 gdi32)

# The XP x86 toolchain (zig 0.11, msvcrt) cannot link -municode, so the 32-bit
# build uses a plain WinMain entry that forwards to wWinMain.
if(CMAKE_SIZEOF_VOID_P EQUAL 4)
    target_sources(StarCraftGhostSetup PRIVATE src/winmain_shim.c src/xp_compat.c)
    target_sources(GhostRecompUninstall PRIVATE src/winmain_shim.c src/xp_compat.c)
else()
    target_link_options(StarCraftGhostSetup PRIVATE -municode)
    target_link_options(GhostRecompUninstall PRIVATE -municode)
endif()
