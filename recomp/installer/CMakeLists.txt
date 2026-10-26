cmake_minimum_required(VERSION 3.20)
project(sghost_setup C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_compile_definitions(WIN32_LEAN_AND_MEAN NOMINMAX UNICODE _UNICODE)

add_executable(StarCraftGhostSetup WIN32 src/setup.cpp)
target_link_options(StarCraftGhostSetup PRIVATE -municode)
target_link_libraries(StarCraftGhostSetup PRIVATE
    gdiplus winmm shell32 shlwapi ole32 uuid advapi32 comdlg32 user32 gdi32)

add_executable(GhostRecompUninstall WIN32 src/uninstall.cpp)
target_link_options(GhostRecompUninstall PRIVATE -municode)
target_link_libraries(GhostRecompUninstall PRIVATE
    shell32 ole32 advapi32 user32 gdi32)
