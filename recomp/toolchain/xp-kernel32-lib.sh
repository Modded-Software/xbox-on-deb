#!/bin/bash
# Make zig 0.11's mingw kernel32 import library Windows-XP-safe.
#
# zig's bundled kernel32.def advertises Vista+/Win8+ entry points, so libstdc++
# and the mingw runtime resolve AcquireSRWLockExclusive, FlsAlloc, GetThreadId,
# GetSystemTimePreciseAsFileTime, K32EnumProcessModules and friends to real
# imports. Windows XP refuses to load an image with unresolved imports, so the
# names are stripped from the def (the .orig file keeps the original) and the
# installer provides XP implementations in src/xp_compat.c.
#
# zig rebuilds its cached import library from this def, so run it once after a
# fresh .venv-mingw32 and before the first ARCH=x86 build.
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(pwd -P)}"
PY="$REPO_ROOT/.venv-mingw32/bin/python"
DEF="$REPO_ROOT/.venv-mingw32/lib/python3.13/site-packages/ziglang/lib/libc/mingw/lib32/kernel32.def"

DROP='^(AcquireSRWLock(Exclusive|Shared)@4|ReleaseSRWLock(Exclusive|Shared)@4|InitializeSRWLock@4|TryAcquireSRWLock(Exclusive|Shared)@4|SleepConditionVariable(SRW|CS)@(16|12)|InitializeConditionVariable@4|Wake(All)?ConditionVariable@4|Fls(Alloc|Free|GetValue|SetValue)@(4|8)|InitOnceExecuteOnce@16|GetThreadId@4|GetSystemTimePreciseAsFileTime@4|K32EnumProcessModules(Ex)?@(16|20))$'

if [ ! -f "$DEF.orig" ]; then
    cp "$DEF" "$DEF.orig"
fi
grep -vE "$DROP" "$DEF.orig" > "$DEF"
echo "patched $DEF (XP-safe kernel32 imports)"
