/* Ubuntu/MinGW layer for GhostPC (MSVC sources).
 * Force-included by tools/ghostpc-ubuntu/build.sh.
 *
 * MSVC structured exception handling is not available in the mingw target, so
 * __try/__except is emulated with a VEH-backed setjmp/longjmp frame stack. The
 * translation keeps MSVC's syntax:
 *
 *     __try { body } __except (EXCEPTION_EXECUTE_HANDLER) { handler }
 *
 * becomes
 *
 *     if (frame; push(frame)) { body } else { handler }
 *
 * The IF-init declaration is scoped to the whole if/else statement, and the
 * cleanup attribute unlinks the frame on every exit path.
 */
#pragma once

#ifdef __cplusplus
extern "C" {
#endif

#include <setjmp.h>

typedef struct GhostUbuntuSehFrame {
    jmp_buf jb;
    struct GhostUbuntuSehFrame *prev;
    int active;
} GhostUbuntuSehFrame;

int  ghost_ubuntu_seh_push(GhostUbuntuSehFrame *frame);
void ghost_ubuntu_seh_pop(GhostUbuntuSehFrame *frame);

#ifdef __cplusplus
}
#endif

#define __try \
    if (GhostUbuntuSehFrame _ghost_seh_frame \
            __attribute__((cleanup(ghost_ubuntu_seh_pop))) = {0}; \
        (ghost_ubuntu_seh_push(&_ghost_seh_frame), setjmp(_ghost_seh_frame.jb) == 0))
#define __except(x) else
#define __finally else
