/* Windows XP wrappers for the 32-bit installer build.
 *
 * The only available 32-bit toolchain that links msvcrt.dll instead of the
 * UCRT is zig 0.11, whose mingw-w64 runtime and libstdc++ import a handful of
 * post-XP kernel32 entry points (SRW locks, fibre local storage, InitOnce,
 * GetThreadId, GetSystemTimePreciseAsFileTime, K32EnumProcessModules). Windows
 * XP refuses to load an image with unresolved imports, so each one is defined
 * here in terms of APIs XP does have.
 *
 * The installer is a single-threaded GUI program, so mapping every SRW lock
 * and condition variable onto one global critical section is safe.
 *
 * Symbols are declared with explicit decorated names (asm labels) because the
 * mingw headers declare them __declspec(dllimport) and redefining those is an
 * error.
 */
typedef void *PVOID;
typedef void *HANDLE;
typedef void *HMODULE;
typedef unsigned long DWORD;
typedef int BOOL;
typedef unsigned char BOOLEAN;
typedef unsigned long ULONG;
typedef long LONG;
typedef unsigned long long ULONG_PTR;
typedef unsigned int UINT;

typedef struct {
    DWORD dwLowDateTime;
    DWORD dwHighDateTime;
} FILETIME;
typedef FILETIME *LPFILETIME;

typedef struct {
    PVOID DebugInfo;
    LONG LockCount;
    LONG RecursionCount;
    HANDLE OwningThread;
    HANDLE LockSemaphore;
    ULONG_PTR SpinCount;
} CRITICAL_SECTION;
typedef CRITICAL_SECTION *PCRITICAL_SECTION;

extern void __stdcall InitializeCriticalSection(PCRITICAL_SECTION);
extern void __stdcall EnterCriticalSection(PCRITICAL_SECTION);
extern void __stdcall LeaveCriticalSection(PCRITICAL_SECTION);
extern void __stdcall Sleep(DWORD);
extern BOOL __stdcall TryEnterCriticalSection(PCRITICAL_SECTION);
extern DWORD __stdcall TlsAlloc(void);
extern BOOL __stdcall TlsFree(DWORD);
extern PVOID __stdcall TlsGetValue(DWORD);
extern BOOL __stdcall TlsSetValue(DWORD, PVOID);
extern DWORD __stdcall GetCurrentThreadId(void);
extern void __stdcall GetSystemTimeAsFileTime(LPFILETIME);
extern LONG __stdcall InterlockedCompareExchange(LONG volatile *, LONG, LONG);

static CRITICAL_SECTION g_xp_lock;
static int g_xp_lock_ready;

static void xp_lock_init(void)
{
    if (!g_xp_lock_ready) {
        InitializeCriticalSection(&g_xp_lock);
        g_xp_lock_ready = 1;
    }
}

/* ---- SRW locks: one global lock stands in for all of them ---- */
void __stdcall xp_acquire_excl(void *) __asm__("_AcquireSRWLockExclusive@4");
void __stdcall xp_acquire_excl(void *lock)
{
    (void)lock;
    xp_lock_init();
    EnterCriticalSection(&g_xp_lock);
}

void __stdcall xp_acquire_shared(void *) __asm__("_AcquireSRWLockShared@4");
void __stdcall xp_acquire_shared(void *lock)
{
    (void)lock;
    xp_lock_init();
    EnterCriticalSection(&g_xp_lock);
}

void __stdcall xp_release_excl(void *) __asm__("_ReleaseSRWLockExclusive@4");
void __stdcall xp_release_excl(void *lock)
{
    (void)lock;
    LeaveCriticalSection(&g_xp_lock);
}

void __stdcall xp_release_shared(void *) __asm__("_ReleaseSRWLockShared@4");
void __stdcall xp_release_shared(void *lock)
{
    (void)lock;
    LeaveCriticalSection(&g_xp_lock);
}

/* ---- condition variables: never used to block in this program ---- */
BOOL __stdcall xp_sleep_cv(void *cv, void *lock, DWORD ms, ULONG flags)
    __asm__("_SleepConditionVariableSRW@16");
BOOL __stdcall xp_sleep_cv(void *cv, void *lock, DWORD ms, ULONG flags)
{
    (void)cv;
    (void)lock;
    (void)flags;
    Sleep(ms);
    return 1;
}

void __stdcall xp_wake_cv(void *cv) __asm__("_WakeConditionVariable@4");
void __stdcall xp_wake_cv(void *cv)
{
    (void)cv;
}

void __stdcall xp_wake_all_cv(void *cv) __asm__("_WakeAllConditionVariable@4");
void __stdcall xp_wake_all_cv(void *cv)
{
    (void)cv;
}

/* ---- fibre local storage maps onto TLS ---- */
DWORD __stdcall xp_fls_alloc(void *cb) __asm__("_FlsAlloc@4");
DWORD __stdcall xp_fls_alloc(void *cb)
{
    (void)cb;
    return TlsAlloc();
}

BOOL __stdcall xp_fls_free(DWORD idx) __asm__("_FlsFree@4");
BOOL __stdcall xp_fls_free(DWORD idx)
{
    return TlsFree(idx);
}

PVOID __stdcall xp_fls_get(DWORD idx) __asm__("_FlsGetValue@4");
PVOID __stdcall xp_fls_get(DWORD idx)
{
    return TlsGetValue(idx);
}

BOOL __stdcall xp_fls_set(DWORD idx, PVOID v) __asm__("_FlsSetValue@8");
BOOL __stdcall xp_fls_set(DWORD idx, PVOID v)
{
    return TlsSetValue(idx, v);
}

/* ---- InitOnce: 0 = idle, 1 = running, 2 = done ---- */
BOOL __stdcall xp_init_once(void *once, void *fn, PVOID param, PVOID *ctx)
    __asm__("_InitOnceExecuteOnce@16");
BOOL __stdcall xp_init_once(void *once, void *fn, PVOID param, PVOID *ctx)
{
    volatile LONG *state = (volatile LONG *)once;
    LONG prev = InterlockedCompareExchange(state, 1, 0);
    if (prev == 0) {
        BOOL ok = ((BOOL(__stdcall *)(PVOID, PVOID *, PVOID *))fn)(once, ctx, param);
        InterlockedCompareExchange(state, 2, 1);
        return ok;
    }
    while (*state != 2)
        Sleep(0);
    return 1;
}

/* ---- misc ---- */
DWORD __stdcall xp_get_thread_id(HANDLE h) __asm__("_GetThreadId@4");
DWORD __stdcall xp_get_thread_id(HANDLE h)
{
    (void)h;
    return GetCurrentThreadId();
}

void __stdcall xp_precise_time(LPFILETIME ft) __asm__("_GetSystemTimePreciseAsFileTime@4");
void __stdcall xp_precise_time(LPFILETIME ft)
{
    GetSystemTimeAsFileTime(ft);
}

BOOL __stdcall xp_enum_modules(HANDLE p, HMODULE *mods, DWORD cb, DWORD *needed)
    __asm__("_K32EnumProcessModules@16");
BOOL __stdcall xp_enum_modules(HANDLE p, HMODULE *mods, DWORD cb, DWORD *needed)
{
    (void)p;
    (void)mods;
    (void)cb;
    if (needed)
        *needed = 0;
    return 0;
}

/* ---- init/try variants: same one-lock stand-in ---- */
void __stdcall xp_init_srw(void *lock) __asm__("_InitializeSRWLock@4");
void __stdcall xp_init_srw(void *lock)
{
    (void)lock;
    xp_lock_init();
}

BOOLEAN __stdcall xp_try_excl(void *lock) __asm__("_TryAcquireSRWLockExclusive@4");
BOOLEAN __stdcall xp_try_excl(void *lock)
{
    (void)lock;
    xp_lock_init();
    return (BOOLEAN)TryEnterCriticalSection(&g_xp_lock);
}

BOOLEAN __stdcall xp_try_shared(void *lock) __asm__("_TryAcquireSRWLockShared@4");
BOOLEAN __stdcall xp_try_shared(void *lock)
{
    (void)lock;
    xp_lock_init();
    return (BOOLEAN)TryEnterCriticalSection(&g_xp_lock);
}

void __stdcall xp_init_cv(void *cv) __asm__("_InitializeConditionVariable@4");
void __stdcall xp_init_cv(void *cv)
{
    (void)cv;
}

BOOL __stdcall xp_sleep_cv_cs(void *cv, PCRITICAL_SECTION cs, DWORD ms, ULONG flags)
    __asm__("_SleepConditionVariableCS@12");
BOOL __stdcall xp_sleep_cv_cs(void *cv, PCRITICAL_SECTION cs, DWORD ms, ULONG flags)
{
    (void)cv;
    (void)cs;
    (void)flags;
    Sleep(ms);
    return 1;
}
