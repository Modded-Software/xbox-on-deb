/* VEH-backed implementation of the __try/__except layer.
 *
 * Instrumentation: GHOSTPC_UBUNTU_TRACE=1 logs each caught hardware exception
 * (code + faulting address) to the log chosen by GHOSTPC_UBUNTU_LOG or
 * ghostpc-ubuntu-build.log beside the executable.
 */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <setjmp.h>
#include "ghostpc_ubuntu_compat.h"

static __declspec(thread) GhostUbuntuSehFrame *g_top;
static PVOID g_veh;
static INIT_ONCE g_once = INIT_ONCE_STATIC_INIT;

static const char *trace_log_path(void)
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

static int trace_enabled(void)
{
    const char *v = getenv("GHOSTPC_UBUNTU_TRACE");
    return v && *v && *v != '0';
}

static void trace_exception(const char *what, EXCEPTION_POINTERS *info)
{
    if (!trace_enabled())
        return;
    FILE *f = fopen(trace_log_path(), "a");
    if (!f)
        return;
    DWORD code = 0;
    void *at = NULL;
    if (info && info->ExceptionRecord) {
        code = info->ExceptionRecord->ExceptionCode;
        at = info->ExceptionRecord->ExceptionAddress;
    }
    fprintf(f, "[SEH] %s code=0x%08lX at=%p tid=%lu\n", what,
            (unsigned long)code, at, (unsigned long)GetCurrentThreadId());
    fclose(f);
}

static LONG CALLBACK seh_veh(EXCEPTION_POINTERS *info)
{
    GhostUbuntuSehFrame *f = g_top;
    if (!f || !f->active)
        return EXCEPTION_CONTINUE_SEARCH;
    /* Let C++ exceptions pass through to the CRT. */
    if (info && info->ExceptionRecord &&
        info->ExceptionRecord->ExceptionCode == 0xE06D7363) {
        trace_exception("cxx-pass", info);
        return EXCEPTION_CONTINUE_SEARCH;
    }
    trace_exception("caught", info);
    f->active = 0;
    g_top = f->prev;
    longjmp(f->jb, 1);
    return EXCEPTION_CONTINUE_SEARCH;
}

static BOOL CALLBACK seh_init(PINIT_ONCE once, PVOID param, PVOID *ctx)
{
    (void)once; (void)param; (void)ctx;
    g_veh = AddVectoredExceptionHandler(1, seh_veh);
    return TRUE;
}

extern "C" int ghost_ubuntu_seh_push(GhostUbuntuSehFrame *frame)
{
    InitOnceExecuteOnce(&g_once, seh_init, NULL, NULL);
    frame->prev = g_top;
    frame->active = 1;
    g_top = frame;
    return 1;
}

extern "C" void ghost_ubuntu_seh_pop(GhostUbuntuSehFrame *frame)
{
    if (!frame || !frame->active)
        return;
    frame->active = 0;
    if (g_top == frame)
        g_top = frame->prev;
}
