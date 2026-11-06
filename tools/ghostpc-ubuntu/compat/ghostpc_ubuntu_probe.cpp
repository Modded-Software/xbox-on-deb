/* Build/runtime stamp for the Ubuntu cross-build.
 *
 * Runs before WinMain (static constructor) and appends one block to
 * GHOSTPC_UBUNTU_LOG (default ghostpc-ubuntu-build.log beside the exe):
 * compiler, build date, Windows/Wine version, and whether the DLLs GhostPC
 * loads dynamically are present in the process search path.
 */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>

static const char *probe_log_path(void)
{
    static char path[MAX_PATH];
    static int done;
    if (done)
        return path;
    done = 1;
    const char *env = getenv("GHOSTPC_UBUNTU_LOG");
    if (env && *env) {
        _snprintf(path, sizeof path, "%s", env);
    } else {
        char exe[MAX_PATH];
        DWORD n = GetModuleFileNameA(NULL, exe, sizeof exe);
        if (n) {
            char *slash = strrchr(exe, '\\');
            if (slash)
                *slash = 0;
        }
        _snprintf(path, sizeof path, "%s\\ghostpc-ubuntu-build.log", exe);
    }
    return path;
}

static void probe_write(void)
{
    FILE *f = fopen(probe_log_path(), "a");
    if (!f)
        return;

    OSVERSIONINFOA vi;
    vi.dwOSVersionInfoSize = sizeof vi;
    GetVersionExA(&vi);

    fprintf(f, "\n=== GhostPC Ubuntu cross-build ===\n");
    fprintf(f, "compiler : %s\n", __VERSION__);
    fprintf(f, "built    : %s %s\n", __DATE__, __TIME__);
    fprintf(f, "windows  : %lu.%lu build %lu (%s)\n",
            (unsigned long)vi.dwMajorVersion, (unsigned long)vi.dwMinorVersion,
            (unsigned long)vi.dwBuildNumber, vi.szCSDVersion);
    fprintf(f, "exe      : %s\n", GetCommandLineA());

    /* Do NOT LoadLibrary here: GhostPC reserves the game image's preferred
     * base (0x00400000) later, in WinMain. A DLL loaded by this early probe
     * can land there under Wine and force the game image to relocate, which
     * corrupts its absolute pointers. Report already-loaded modules only. */
    static const char *dlls[] = {"d3d9.dll", "d3dcompiler_47.dll", "xinput9_1_0.dll",
                                 "xinput1_4.dll", "xaudio2_9.dll", "dbghelp.dll"};
    for (unsigned i = 0; i < sizeof dlls / sizeof dlls[0]; i++) {
        HMODULE m = GetModuleHandleA(dlls[i]);
        fprintf(f, "dll      : %-22s %s\n", dlls[i], m ? "already loaded" : "not loaded yet");
    }
    fclose(f);
}

struct GhostUbuntuProbe {
    GhostUbuntuProbe() { probe_write(); }
};

static GhostUbuntuProbe g_ghost_ubuntu_probe;
