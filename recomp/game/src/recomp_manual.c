/**
 * Manual function overrides and ICALL diagnostics
 *
 * This file provides:
 *   - recomp_lookup_manual()  : intercept specific Xbox VAs with hand-written code
 *   - recomp_icall_fail_log() : log when an indirect call target can't be resolved
 *   - ICALL trace ring buffer  : globals used by the RECOMP_ICALL macro
 *
 * The recomp pipeline generates an auto-dispatch table (recomp_lookup) that
 * resolves most function addresses. recomp_lookup_manual() is called FIRST,
 * giving you a chance to override any function with a custom implementation.
 *
 * Common reasons to add manual overrides:
 *   - Trace a function to understand call flow (wrap the generated version)
 *   - Fix a function the lifter translated incorrectly
 *   - Stub out a function that crashes (return early, set eax to a safe value)
 *   - Redirect a function to a native implementation (e.g., skip CRT init)
 *   - Intercept D3D/audio calls for custom rendering or sound
 */

#include <stdio.h>
#include <stdint.h>

/* ── ICALL trace ring buffer ───────────────────────────────── */

/*
 * These globals are written by the RECOMP_ICALL macro (defined in
 * recomp_types.h) every time an indirect call is dispatched. When a
 * crash occurs, the VEH handler or recomp_icall_fail_log() can dump
 * the last 16 call targets to help you trace what happened.
 *
 * The runtime owns them: xbox_kernel defines all three in
 * src/kernel/xbox_memory_layout.c, and recomp_types.h declares them extern.
 * Declare, do not define -- a definition here as well is a duplicate symbol,
 * and a project copied from this template failed to link on all three:
 *
 *   xbox_memory_layout.obj : error LNK2005: g_icall_count already defined
 *                            in recomp_manual.obj
 */
extern volatile uint32_t g_icall_trace[16];
extern volatile uint32_t g_icall_trace_idx;
extern volatile uint64_t g_icall_count;

typedef void (*recomp_func_t)(void);

/* Lifted by hand because the disassembler missed the vtable entry; defined at
 * the bottom of this file. See recomp_lookup_manual. */
void fixed_cCloakShader_RenderSetup_0021D7E0(void);

/* ── Register state (defined in xbox_memory_layout.c; declared by
 * recomp_types.h, included at the bottom of this file) ──────── */

extern ptrdiff_t g_xbox_mem_offset;

/* ── Manual function overrides ─────────────────────────────── */

/*
 * Return a function pointer to override the given Xbox VA, or NULL
 * to fall through to the auto-generated dispatch table.
 *
 * This is called on every indirect call (RECOMP_ICALL) and every
 * direct call through the dispatch table, so keep it fast. A chain
 * of if-statements on uint32_t compiles to a simple comparison
 * sequence; for large override tables, consider a sorted array
 * with binary search.
 *
 * Examples of common override patterns:
 *
 *   // Trace wrapper: log entry/exit around the generated function
 *   extern void sub_00012345(void);
 *   static void traced_sub_00012345(void) {
 *       fprintf(stderr, "[TRACE] sub_00012345 entered, eax=0x%08X\n", g_eax);
 *       sub_00012345();
 *       fprintf(stderr, "[TRACE] sub_00012345 returned, eax=0x%08X\n", g_eax);
 *   }
 *
 *   // Stub: skip a function entirely (return 0 in eax)
 *   static void stub_00067890(void) {
 *       g_eax = 0;
 *   }
 *
 *   // Fix: replace a broken lifted function with correct C
 *   static void fixed_sub_000ABCDE(void) {
 *       // Read arguments from stack/registers per calling convention
 *       uint32_t arg1 = g_ecx;
 *       uint32_t arg2 = MEM32(g_esp + 4);
 *       // ... correct implementation ...
 *       g_eax = result;
 *   }
 */
recomp_func_t recomp_lookup_manual(uint32_t xbox_va)
{
    /*
     * TODO: Add your overrides here. Examples:
     *
     * if (xbox_va == 0x00012345) return traced_sub_00012345;
     * if (xbox_va == 0x00067890) return stub_00067890;
     * if (xbox_va == 0x000ABCDE) return fixed_sub_000ABCDE;
     */

    /* cCloakShader::RenderSetup. The disassembler missed this vtable entry, so
     * it was never lifted and every cloak render call hit recomp_icall_fail_log
     * and did nothing (eax=0). map: 0x0021D7E0 = this method. */
    if (xbox_va == 0x0021D7E0u)
        return fixed_cCloakShader_RenderSetup_0021D7E0;

    (void)xbox_va;
    return (recomp_func_t)0;
}

/* ── ICALL failure logging ─────────────────────────────────── */

/*
 * Called when RECOMP_ICALL cannot resolve a target address.
 * This usually means one of:
 *   - A vtable dispatch to an address not in the dispatch table
 *   - A function pointer loaded from uninitialized or corrupt memory
 *   - A kernel thunk address that the bridge doesn't handle
 *
 * During early bring-up you will see many of these. Most are harmless
 * (the ICALL macro pops the dummy return address and continues).
 * Focus on the ones that cause crashes or incorrect behavior.
 */
void recomp_icall_fail_log(uint32_t va)
{
    fprintf(stderr, "[ICALL] Failed to resolve VA 0x%08X (total calls: %llu)\n",
            va, (unsigned long long)g_icall_count);

    /* Dump last 16 call targets from the ring buffer */
    fprintf(stderr, "  Recent ICALL targets:\n");
    for (int i = 0; i < 16; i++) {
        int idx = (g_icall_trace_idx - 16 + i) & 15;
        if (g_icall_trace[idx])
            fprintf(stderr, "    [%2d] 0x%08X\n", i, g_icall_trace[idx]);
    }
    fflush(stderr);
}

/* An indirect call whose target is not code: a null or wild function pointer.
 *
 * Skipping these is right -- calling a data address is worse -- but skipping
 * them *silently* is not. They almost always arrive inside a loop, so the
 * symptom is a hang with no output rather than a diagnosable null vtable call.
 *
 * Rate-limited per address: a spin can produce millions of these, and the
 * useful information is which addresses occur, not how often.
 */
void recomp_icall_not_code_log(uint32_t va)
{
    enum { SLOTS = 16 };
    static uint32_t seen[SLOTS];
    static uint64_t hits[SLOTS];
    static int count;
    int i;

    for (i = 0; i < count; i++)
        if (seen[i] == va)
            break;
    if (i == count) {
        if (count == SLOTS)
            return;
        seen[count] = va;
        hits[count] = 0;
        count++;
    }
    hits[i]++;
    /* Report at 1, 10, 100, 1000 ... rather than once. A single line says a
     * wild pointer was skipped; the progression says it is being skipped in a
     * loop, which is the difference between a curiosity and the reason the
     * title is hung. */
    {
        uint64_t n = hits[i];
        while (n >= 10 && n % 10 == 0)
            n /= 10;
        if (n != 1)
            return;
    }
    fprintf(stderr, "[ICALL] target 0x%08X is not code -- skipped %llu time(s) "
                    "(null or wild function pointer, at call #%llu)\n",
            va, (unsigned long long)hits[i],
            (unsigned long long)g_icall_count);
    fflush(stderr);
}

/* ── Untranslated instructions ───────────────────────────────────────────
 *
 * The lifter emits RECOMP_UNIMPL(text, va) at every instruction it has no
 * translation for, in place of the bare comment it used to leave. The
 * instruction is still a no-op; this only stops the omission being silent.
 * RECOMP_UNIMPL_TRAP=1 aborts at the first hit, at the guest address of the
 * cause rather than wherever the damage surfaces. */
#include <stdlib.h>

void recomp_unimpl(const char *text, uint32_t va)
{
    static int printed;
    const char *trap = getenv("RECOMP_UNIMPL_TRAP");
    int stop = trap && *trap && *trap != '0';

    if (printed < 50 || stop) {
        printed++;
        fprintf(stderr,
                "[UNIMPL] untranslated instruction REACHED: `%s` at 0x%08X"
                " (a no-op; set RECOMP_UNIMPL_TRAP=1 to stop here)\n",
                text, va);
        fflush(stderr);
    }
    if (stop) abort();
}

/* -- cCloakShader::RenderSetup (0x0021D7E0) -----------------------------
 * The disassembler never detected this vtable entry, so it stayed out of
 * recomp_funcs.h and every indirect call to it resolved to nothing (eax=0):
 * the cloak render setup never ran and Nova cloak rendering was broken.
 * Lifted by hand with tools.recomp. Durable fix: the 0x0021D7E0 seed in
 * config/seed_functions.json + a full regen. */
#define RECOMP_GENERATED_CODE
#include "recomp_funcs.h"

/**
 * fixed_cCloakShader_RenderSetup_0021D7E0
 * Original: 0x0021D7E0 - 0x0021DCB4 (1236 bytes, 329 insns)
 * Category: game_render
 * CC: cdecl, 2 params, returns int_or_void
 * Frame: fpo_leaf
 */
void fixed_cCloakShader_RenderSetup_0021D7E0(void)
{
    int _flags = 0; /* fallback flag var */
    uint32_t _fa = 0, _fb = 0;
    int32_t _fas = 0, _fbs = 0;
    (void)_fa; (void)_fb; (void)_fas; (void)_fbs;
    double _fca = 0.0, _fcb = 0.0;
    (void)_fca; (void)_fcb;

loc_0021D7E0: ;
    eax = MEM32(0x491CF8);
    PUSH32(esp, ebx);
    PUSH32(esp, esi);
    ebx = 0; /* xor self */
    _fa = (uint32_t)(ebx) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* xor result */
    MEM32(0x4BBCF0) = ebx;
    PUSH32(esp, edi);
    edi = ecx;
    ecx = MEM32(eax + 4);
    ecx = MEM32(ecx + 0x20);
    edx = MEM32(ecx + 0x168);
    eax = MEM32(ecx + 0x164);
    eax = edx + eax + -1;
    edx = ((int32_t)eax < 0) ? 0xFFFFFFFF : 0; /* cdq */
    esi = 0x50;
    { int64_t _dividend = ((int64_t)(int32_t)edx << 32) | eax;
      eax = (uint32_t)((int32_t)(_dividend / (int32_t)esi));
      edx = (uint32_t)((int32_t)(_dividend % (int32_t)esi)); }
    eax = ecx + edx * 4 + 0x24;
    MEM32(eax) = MEM32(eax) + 1;
    _fa = (uint32_t)(MEM32(eax)) & 0xFFFFFFFFu;
    _fas = (int32_t)(int32_t)(_fa); _fb = (_fa == 0x80000000u); /* inc result/SF/OF; CF unchanged */
    _fa = (uint32_t)(MEM32(0x4BBD00)) & 0xFFFFFFFFu; _fb = (uint32_t)(ebx) & 0xFFFFFFFFu;
    _fas = (int32_t)(int32_t)(_fa); _fbs = (int32_t)(int32_t)(_fb); /* cmp MEM32(0x4BBD00), ebx (32-bit) */
    if (CMP_EQ(_fa, _fb)) goto loc_0021D82A; /* je: equal / zero */

loc_0021D81E: ;
    PUSH32(esp, ebx);
    MEM32(0x4BBD00) = ebx;
    PUSH32(esp, 0x0021D82Au); RECOMP_ABI_CALL(0x002C0AE0u, D3DDevice_SetRenderState_ZBias_4_002C0AE0); /* call 0x002C0AE0 */

loc_0021D82A: ;
    eax = MEM32(0x4BBD34);
    esi = 2;
    _fa = (uint32_t)(eax) & 0xFFFFFFFFu; _fb = (uint32_t)(esi) & 0xFFFFFFFFu;
    _fas = (int32_t)(int32_t)(_fa); _fbs = (int32_t)(int32_t)(_fb); /* cmp eax, esi (32-bit) */
    if (CMP_EQ(_fa, _fb)) goto loc_0021D844; /* je: equal / zero */

loc_0021D838: ;
    PUSH32(esp, esi);
    PUSH32(esp, 0x0021D83Eu); RECOMP_ABI_CALL(0x002C1720u, D3DDevice_SetRenderState_ZEnable_4_002C1720); /* call 0x002C1720 */

loc_0021D83E: ;
    MEM32(0x4BBD34) = esi;

loc_0021D844: ;
    eax = MEM32(0x4BBD30);
    esi = 1;
    _fa = (uint32_t)(eax) & 0xFFFFFFFFu; _fb = (uint32_t)(esi) & 0xFFFFFFFFu;
    _fas = (int32_t)(int32_t)(_fa); _fbs = (int32_t)(int32_t)(_fb); /* cmp eax, esi (32-bit) */
    if (CMP_EQ(_fa, _fb)) goto loc_0021D864; /* je: equal / zero */

loc_0021D852: ;
    edx = esi;
    ecx = 0x4035C;
    PUSH32(esp, 0x0021D85Eu); RECOMP_ABI_CALL(0x002C04D0u, D3DDevice_SetRenderState_Simple_8_002C04D0); /* call 0x002C04D0 */

loc_0021D85E: ;
    MEM32(0x4BBD30) = esi;

loc_0021D864: ;
    eax = MEM32(0x4BBD38);
    edx = 0x203;
    _fa = (uint32_t)(eax) & 0xFFFFFFFFu; _fb = (uint32_t)(edx) & 0xFFFFFFFFu;
    _fas = (int32_t)(int32_t)(_fa); _fbs = (int32_t)(int32_t)(_fb); /* cmp eax, edx (32-bit) */
    if (CMP_EQ(_fa, _fb)) goto loc_0021D882; /* je: equal / zero */

loc_0021D872: ;
    ecx = 0x40354;
    MEM32(0x4BBD38) = edx;
    PUSH32(esp, 0x0021D882u); RECOMP_ABI_CALL(0x002C04D0u, D3DDevice_SetRenderState_Simple_8_002C04D0); /* call 0x002C04D0 */

loc_0021D882: ;
    _fa = (uint32_t)(MEM32(0x4BBCF8)) & 0xFFFFFFFFu; _fb = (uint32_t)(esi) & 0xFFFFFFFFu;
    _fas = (int32_t)(int32_t)(_fa); _fbs = (int32_t)(int32_t)(_fb); /* cmp MEM32(0x4BBCF8), esi (32-bit) */
    if (CMP_EQ(_fa, _fb)) goto loc_0021D895; /* je: equal / zero */

loc_0021D88A: ;
    PUSH32(esp, esi);
    ecx = 0x4BBCF0;
    PUSH32(esp, 0x0021D895u); RECOMP_ABI_CALL(0x00206E70u, cRenderState_DoSetAlphaBlend_00206E70); /* call 0x00206E70 */

loc_0021D895: ;
    ecx = MEM32(0x4BBCFC);
    eax = 0x900;
    _fa = (uint32_t)(ecx) & 0xFFFFFFFFu; _fb = (uint32_t)(eax) & 0xFFFFFFFFu;
    _fas = (int32_t)(int32_t)(_fa); _fbs = (int32_t)(int32_t)(_fb); /* cmp ecx, eax (32-bit) */
    if (CMP_EQ(_fa, _fb)) goto loc_0021D8AF; /* je: equal / zero */

loc_0021D8A4: ;
    PUSH32(esp, eax);
    MEM32(0x4BBCFC) = eax;
    PUSH32(esp, 0x0021D8AFu); RECOMP_ABI_CALL(0x002C08A0u, D3DDevice_SetRenderState_CullMode_4_002C08A0); /* call 0x002C08A0 */

loc_0021D8AF: ;
    _fa = (uint32_t)(MEM32(0x4BBD18)) & 0xFFFFFFFFu; _fb = (uint32_t)(ebx) & 0xFFFFFFFFu;
    _fas = (int32_t)(int32_t)(_fa); _fbs = (int32_t)(int32_t)(_fb); /* cmp MEM32(0x4BBD18), ebx (32-bit) */
    if (CMP_EQ(_fa, _fb)) goto loc_0021D8C9; /* je: equal / zero */

loc_0021D8B7: ;
    edx = 0; /* xor self */
    _fa = (uint32_t)(edx) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* xor result */
    ecx = 0x40300;
    PUSH32(esp, 0x0021D8C3u); RECOMP_ABI_CALL(0x002C04D0u, D3DDevice_SetRenderState_Simple_8_002C04D0); /* call 0x002C04D0 */

loc_0021D8C3: ;
    MEM32(0x4BBD18) = ebx;

loc_0021D8C9: ;
    _fa = (uint32_t)(MEM32(0x4BBD00)) & 0xFFFFFFFFu; _fb = (uint32_t)(ebx) & 0xFFFFFFFFu;
    _fas = (int32_t)(int32_t)(_fa); _fbs = (int32_t)(int32_t)(_fb); /* cmp MEM32(0x4BBD00), ebx (32-bit) */
    if (CMP_EQ(_fa, _fb)) goto loc_0021D8DD; /* je: equal / zero */

loc_0021D8D1: ;
    PUSH32(esp, ebx);
    MEM32(0x4BBD00) = ebx;
    PUSH32(esp, 0x0021D8DDu); RECOMP_ABI_CALL(0x002C0AE0u, D3DDevice_SetRenderState_ZBias_4_002C0AE0); /* call 0x002C0AE0 */

loc_0021D8DD: ;
    _fa = (uint32_t)(MEM32(edi + 0x58)) & 0xFFFFFFFFu; _fb = (uint32_t)(ebx) & 0xFFFFFFFFu;
    _fas = (int32_t)(int32_t)(_fa); _fbs = (int32_t)(int32_t)(_fb); /* cmp MEM32(edi + 0x58), ebx (32-bit) */
    if (CMP_NE(_fa, _fb)) goto loc_0021D8F8; /* jne: not equal / not zero */

loc_0021D8E2: ;
    _fa = (uint32_t)(MEM32(edi + 0x5C)) & 0xFFFFFFFFu; _fb = (uint32_t)(ebx) & 0xFFFFFFFFu;
    _fas = (int32_t)(int32_t)(_fa); _fbs = (int32_t)(int32_t)(_fb); /* cmp MEM32(edi + 0x5C), ebx (32-bit) */
    if (CMP_NE(_fa, _fb)) goto loc_0021D8F8; /* jne: not equal / not zero */

loc_0021D8E7: ;
    xmm0 = XMM_SCALAR(MEMF(0x361CD0)); /* movss */
    _fca = xmm0.f[0]; _fcb = MEMF(edi + 0x70); /* comiss */
    if ((_fca > _fcb)) goto loc_0021D8F8; /* ja: above (unsigned >) (xmm0.f[0] vs MEMF(edi + 0x70)) */

loc_0021D8F5: ;
    PUSH32(esp, ebx);
    goto loc_0021D8F9;

loc_0021D8F8: ;
    PUSH32(esp, esi);

loc_0021D8F9: ;
    ecx = 0x4BBCF0;
    PUSH32(esp, 0x0021D903u); RECOMP_ABI_CALL(0x00031170u, cRenderState_SetLighting_00031170); /* call 0x00031170 */

loc_0021D903: ;
    PUSH32(esp, ebx);
    ecx = 0x4BBCF0;
    PUSH32(esp, 0x0021D90Eu); RECOMP_ABI_CALL(0x00206730u, cRenderState_SetFogMode_00206730); /* call 0x00206730 */

loc_0021D90E: ;
    PUSH32(esp, ebx);
    PUSH32(esp, ebx);
    PUSH32(esp, 0x0021D915u); RECOMP_ABI_CALL(0x00205CA0u, rlMain_GetBackBufferTexture_00205CA0); /* call 0x00205CA0 */

loc_0021D915: ;
    _fb = (uint32_t)(8) & 0xFFFFFFFFu; _fbs = (int32_t)(int32_t)(_fb); /* add source, before the write */
    esp = esp + 8;
    _fa = (uint32_t)(esp) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* add result */
    PUSH32(esp, eax);
    ecx = 0x4BBC80;
    PUSH32(esp, 0x0021D923u); RECOMP_ABI_CALL(0x0002E840u, cRenderStage_SetTexture_0002E840); /* call 0x0002E840 */

loc_0021D923: ;
    esi = 3;
    PUSH32(esp, esi);
    ecx = 0x4BBC80;
    PUSH32(esp, 0x0021D933u); RECOMP_ABI_CALL(0x00206F60u, cRenderStage_SetColorOp_00206F60); /* call 0x00206F60 */

loc_0021D933: ;
    PUSH32(esp, 4);
    ecx = 0x4BBC80;
    PUSH32(esp, 0x0021D93Fu); RECOMP_ABI_CALL(0x00206A80u, cRenderStage_SetAlphaOp_00206A80); /* call 0x00206A80 */

loc_0021D93F: ;
    eax = MEM32(0x4BBC94);
    ecx = MEM32(0x4BBC80);
    edx = 1;
    _fa = (uint32_t)(eax) & 0xFFFFFFFFu; _fb = (uint32_t)(edx) & 0xFFFFFFFFu;
    _fas = (int32_t)(int32_t)(_fa); _fbs = (int32_t)(int32_t)(_fb); /* cmp eax, edx (32-bit) */
    if (CMP_EQ(_fa, _fb)) goto loc_0021D987; /* je: equal / zero */

loc_0021D953: ;
    ebx = MEM32(0x2D1CA8);
    MEM32(0x4BBC94) = edx;
    edx = edx << LO8(ecx);
    _fa = (uint32_t)(edx) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* shift result */
    eax = ecx;
    eax = eax << 7;
    _fa = (uint32_t)(eax) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* shift result */
    MEM32(eax + 0x2D1CB0) = esi;
    ebx = ebx | edx;
    _fa = (uint32_t)(ebx) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* or result */
    MEM32(eax + 0x2D1CB4) = esi;
    MEM32(0x2D1CA8) = ebx;
    MEM32(eax + 0x2D1CB8) = esi;
    ebx = 0; /* xor self */
    _fa = (uint32_t)(ebx) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* xor result */
    edx = 1;

loc_0021D987: ;
    _fa = (uint32_t)(MEM32(0x4BBC8C)) & 0xFFFFFFFFu; _fb = (uint32_t)(edx) & 0xFFFFFFFFu;
    _fas = (int32_t)(int32_t)(_fa); _fbs = (int32_t)(int32_t)(_fb); /* cmp MEM32(0x4BBC8C), edx (32-bit) */
    if (CMP_EQ(_fa, _fb)) goto loc_0021D9BF; /* je: equal / zero */

loc_0021D98F: ;
    esi = MEM32(0x2D1CA8);
    eax = ecx;
    eax = eax << 7;
    _fa = (uint32_t)(eax) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* shift result */
    MEM32(eax + 0x2D1CBC) = edx;
    MEM32(0x4BBC8C) = edx;
    edx = edx << LO8(ecx);
    _fa = (uint32_t)(edx) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* shift result */
    MEM32(eax + 0x2D1CC0) = 1;
    esi = esi | edx;
    _fa = (uint32_t)(esi) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* or result */
    MEM32(0x2D1CA8) = esi;
    edx = 1;

loc_0021D9BF: ;
    _fa = (uint32_t)(MEM32(0x4BBC90)) & 0xFFFFFFFFu; _fb = (uint32_t)(ebx) & 0xFFFFFFFFu;
    _fas = (int32_t)(int32_t)(_fa); _fbs = (int32_t)(int32_t)(_fb); /* cmp MEM32(0x4BBC90), ebx (32-bit) */
    if (CMP_EQ(_fa, _fb)) goto loc_0021D9E8; /* je: equal / zero */

loc_0021D9C7: ;
    esi = MEM32(0x2D1CA8);
    edx = edx << LO8(ecx);
    _fa = (uint32_t)(edx) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* shift result */
    MEM32(0x4BBC90) = ebx;
    esi = esi | edx;
    _fa = (uint32_t)(esi) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* or result */
    edx = ecx;
    edx = edx << 7;
    _fa = (uint32_t)(edx) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* shift result */
    MEM32(0x2D1CA8) = esi;
    MEM32(edx + 0x2D1CC4) = ebx;

loc_0021D9E8: ;
    PUSH32(esp, ebx);
    PUSH32(esp, ecx);
    PUSH32(esp, 0x0021D9EFu); RECOMP_ABI_CALL(0x002C0D40u, D3DDevice_SetTextureState_TexCoordIndex_8_002C0D40); /* call 0x002C0D40 */

loc_0021D9EF: ;
    edx = MEM32(0x2D1CA8);
    eax = MEM32(0x4BBC80);
    eax = eax << 7;
    _fa = (uint32_t)(eax) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* shift result */
    edx = edx | 0x400;
    _fa = (uint32_t)(edx) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* or result */
    MEM32(0x2D1CA8) = edx;
    MEM32(eax + 0x2D1D04) = ebx;
    _fa = (uint32_t)(MEM32(edi + 0x54)) & 0xFFFFFFFFu; _fb = (uint32_t)(ebx) & 0xFFFFFFFFu;
    _fas = (int32_t)(int32_t)(_fa); _fbs = (int32_t)(int32_t)(_fb); /* cmp MEM32(edi + 0x54), ebx (32-bit) */
    if (CMP_EQ(_fa, _fb)) goto loc_0021DA24; /* je: equal / zero */

loc_0021DA14: ;
    ecx = MEM32(edi + 0x1C);
    PUSH32(esp, ecx);
    ecx = 0x3E2120;
    PUSH32(esp, 0x0021DA22u); RECOMP_ABI_CALL(0x0002E840u, cRenderStage_SetTexture_0002E840); /* call 0x0002E840 */

loc_0021DA22: ;
    goto loc_0021DA68;

loc_0021DA24: ;
    _fa = (uint32_t)(MEM32(0x3E2148)) & 0xFFFFFFFFu; _fb = (uint32_t)(ebx) & 0xFFFFFFFFu;
    _fas = (int32_t)(int32_t)(_fa); _fbs = (int32_t)(int32_t)(_fb); /* cmp MEM32(0x3E2148), ebx (32-bit) */
    if (CMP_EQ(_fa, _fb)) goto loc_0021DA68; /* je: equal / zero */

loc_0021DA2C: ;
    edx = MEM32(0x3E2120);
    PUSH32(esp, ebx);
    PUSH32(esp, edx);
    PUSH32(esp, 0x0021DA39u); RECOMP_ABI_CALL(0x002C31C0u, D3DDevice_SetTexture_8_002C31C0); /* call 0x002C31C0 */

loc_0021DA39: ;
    eax = MEM32(0x491CF8);
    MEM32(0x3E2148) = ebx;
    ecx = MEM32(eax + 4);
    ecx = MEM32(ecx + 0x14);
    edx = MEM32(ecx + 0x168);
    eax = MEM32(ecx + 0x164);
    eax = edx + eax + -1;
    edx = ((int32_t)eax < 0) ? 0xFFFFFFFF : 0; /* cdq */
    esi = 0x50;
    { int64_t _dividend = ((int64_t)(int32_t)edx << 32) | eax;
      eax = (uint32_t)((int32_t)(_dividend / (int32_t)esi));
      edx = (uint32_t)((int32_t)(_dividend % (int32_t)esi)); }
    eax = ecx + edx * 4 + 0x24;
    MEM32(eax) = MEM32(eax) + 1;
    _fa = (uint32_t)(MEM32(eax)) & 0xFFFFFFFFu;
    _fas = (int32_t)(int32_t)(_fa); _fb = (_fa == 0x80000000u); /* inc result/SF/OF; CF unchanged */

loc_0021DA68: ;
    PUSH32(esp, 1);
    esi = 2;
    PUSH32(esp, esi);
    PUSH32(esp, 1);
    PUSH32(esp, esi);
    PUSH32(esp, 0xE);
    ecx = 0x3E2120;
    PUSH32(esp, 0x0021DA7Fu); RECOMP_ABI_CALL(0x00054D70u, cRenderStage_SetCustomColorOp_00054D70); /* call 0x00054D70 */

loc_0021DA7F: ;
    PUSH32(esp, esi);
    ecx = 0x3E2120;
    PUSH32(esp, 0x0021DA8Au); RECOMP_ABI_CALL(0x00206A80u, cRenderStage_SetAlphaOp_00206A80); /* call 0x00206A80 */

loc_0021DA8A: ;
    ecx = MEM32(0x3E2120);
    PUSH32(esp, 1);
    PUSH32(esp, ecx);
    PUSH32(esp, 0x0021DA98u); RECOMP_ABI_CALL(0x002C0D40u, D3DDevice_SetTextureState_TexCoordIndex_8_002C0D40); /* call 0x002C0D40 */

loc_0021DA98: ;
    MEM32(0x2D1CA8) = MEM32(0x2D1CA8) | 0x400;
    _fa = (uint32_t)(MEM32(0x2D1CA8)) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* or result */
    edx = MEM32(0x3E2120);
    edx = edx << 7;
    _fa = (uint32_t)(edx) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* shift result */
    ecx = 0x3E2120;
    MEM32(edx + 0x2D1D04) = ebx;
    PUSH32(esp, 0x0021DABBu); RECOMP_ABI_CALL(0x0020AE80u, cRenderStage_SetMirrorMode_0020AE80); /* call 0x0020AE80 */

loc_0021DABB: ;
    _fa = (uint32_t)(MEM32(0x3E212C)) & 0xFFFFFFFFu; _fb = (uint32_t)(esi) & 0xFFFFFFFFu;
    _fas = (int32_t)(int32_t)(_fa); _fbs = (int32_t)(int32_t)(_fb); /* cmp MEM32(0x3E212C), esi (32-bit) */
    ecx = MEM32(0x3E2120);
    if (CMP_EQ(_fa, _fb)) goto loc_0021DAFE; /* je: equal / zero */

loc_0021DAC9: ;
    eax = ecx;
    eax = eax << 7;
    _fa = (uint32_t)(eax) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* shift result */
    edx = 1;
    MEM32(eax + 0x2D1CBC) = esi;
    MEM32(0x3E212C) = esi;
    esi = MEM32(0x2D1CA8);
    edx = edx << LO8(ecx);
    _fa = (uint32_t)(edx) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* shift result */
    MEM32(eax + 0x2D1CC0) = 2;
    esi = esi | edx;
    _fa = (uint32_t)(esi) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* or result */
    MEM32(0x2D1CA8) = esi;
    esi = 2;

loc_0021DAFE: ;
    _fa = (uint32_t)(MEM32(0x3E2130)) & 0xFFFFFFFFu; _fb = (uint32_t)(ebx) & 0xFFFFFFFFu;
    _fas = (int32_t)(int32_t)(_fa); _fbs = (int32_t)(int32_t)(_fb); /* cmp MEM32(0x3E2130), ebx (32-bit) */
    if (CMP_EQ(_fa, _fb)) goto loc_0021DB2A; /* je: equal / zero */

loc_0021DB06: ;
    edx = MEM32(0x2D1CA8);
    eax = 1;
    eax = eax << LO8(ecx);
    _fa = (uint32_t)(eax) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* shift result */
    MEM32(0x3E2130) = ebx;
    edx = edx | eax;
    _fa = (uint32_t)(edx) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* or result */
    ecx = ecx << 7;
    _fa = (uint32_t)(ecx) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* shift result */
    MEM32(0x2D1CA8) = edx;
    MEM32(ecx + 0x2D1CC4) = ebx;

loc_0021DB2A: ;
    _fa = (uint32_t)(MEM32(edi + 0x58)) & 0xFFFFFFFFu; _fb = (uint32_t)(ebx) & 0xFFFFFFFFu;
    _fas = (int32_t)(int32_t)(_fa); _fbs = (int32_t)(int32_t)(_fb); /* cmp MEM32(edi + 0x58), ebx (32-bit) */
    if (CMP_EQ(_fa, _fb)) goto loc_0021DB96; /* je: equal / zero */

loc_0021DB2F: ;
    PUSH32(esp, 1);
    PUSH32(esp, 0x23);
    PUSH32(esp, 1);
    PUSH32(esp, esi);
    PUSH32(esp, 0x18);
    ecx = 0x3E2190;
    PUSH32(esp, 0x0021DB42u); RECOMP_ABI_CALL(0x00054D70u, cRenderStage_SetCustomColorOp_00054D70); /* call 0x00054D70 */

loc_0021DB42: ;
    PUSH32(esp, 4);
    ecx = 0x3E2190;
    PUSH32(esp, 0x0021DB4Eu); RECOMP_ABI_CALL(0x00206A80u, cRenderStage_SetAlphaOp_00206A80); /* call 0x00206A80 */

loc_0021DB4E: ;
    ecx = MEM32(edi + 0x20);
    PUSH32(esp, ecx);
    ecx = 0x3E2190;
    PUSH32(esp, 0x0021DB5Cu); RECOMP_ABI_CALL(0x0002E840u, cRenderStage_SetTexture_0002E840); /* call 0x0002E840 */

loc_0021DB5C: ;
    ecx = 0x3E2190;
    PUSH32(esp, 0x0021DB66u); RECOMP_ABI_CALL(0x00171FE0u, cRenderStage_SetWrapDefault_00171FE0); /* call 0x00171FE0 */

loc_0021DB66: ;
    PUSH32(esp, 1);
    PUSH32(esp, 0x23);
    PUSH32(esp, 1);
    PUSH32(esp, esi);
    PUSH32(esp, 0x18);
    ecx = 0x3E2200;
    PUSH32(esp, 0x0021DB79u); RECOMP_ABI_CALL(0x00054D70u, cRenderStage_SetCustomColorOp_00054D70); /* call 0x00054D70 */

loc_0021DB79: ;
    PUSH32(esp, 4);
    ecx = 0x3E2200;
    PUSH32(esp, 0x0021DB85u); RECOMP_ABI_CALL(0x00206A80u, cRenderStage_SetAlphaOp_00206A80); /* call 0x00206A80 */

loc_0021DB85: ;
    ecx = 0x3E2200;
    PUSH32(esp, 0x0021DB8Fu); RECOMP_ABI_CALL(0x00171FE0u, cRenderStage_SetWrapDefault_00171FE0); /* call 0x00171FE0 */

loc_0021DB8F: ;
    PUSH32(esp, 0x10);
    goto loc_0021DC2A;

loc_0021DB96: ;
    _fa = (uint32_t)(MEM32(edi + 0x5C)) & 0xFFFFFFFFu; _fb = (uint32_t)(ebx) & 0xFFFFFFFFu;
    _fas = (int32_t)(int32_t)(_fa); _fbs = (int32_t)(int32_t)(_fb); /* cmp MEM32(edi + 0x5C), ebx (32-bit) */
    if (CMP_EQ(_fa, _fb)) goto loc_0021DBFF; /* je: equal / zero */

loc_0021DB9B: ;
    PUSH32(esp, 1);
    PUSH32(esp, 0x23);
    PUSH32(esp, 1);
    PUSH32(esp, esi);
    PUSH32(esp, 0x18);
    ecx = 0x3E2190;
    PUSH32(esp, 0x0021DBAEu); RECOMP_ABI_CALL(0x00054D70u, cRenderStage_SetCustomColorOp_00054D70); /* call 0x00054D70 */

loc_0021DBAE: ;
    PUSH32(esp, 4);
    ecx = 0x3E2190;
    PUSH32(esp, 0x0021DBBAu); RECOMP_ABI_CALL(0x00206A80u, cRenderStage_SetAlphaOp_00206A80); /* call 0x00206A80 */

loc_0021DBBA: ;
    edx = MEM32(edi + 0x28);
    PUSH32(esp, edx);
    ecx = 0x3E2190;
    PUSH32(esp, 0x0021DBC8u); RECOMP_ABI_CALL(0x0002E840u, cRenderStage_SetTexture_0002E840); /* call 0x0002E840 */

loc_0021DBC8: ;
    ecx = 0x3E2190;
    PUSH32(esp, 0x0021DBD2u); RECOMP_ABI_CALL(0x00171FE0u, cRenderStage_SetWrapDefault_00171FE0); /* call 0x00171FE0 */

loc_0021DBD2: ;
    PUSH32(esp, 1);
    PUSH32(esp, 0x23);
    PUSH32(esp, 1);
    PUSH32(esp, esi);
    PUSH32(esp, 0x18);
    ecx = 0x3E2200;
    PUSH32(esp, 0x0021DBE5u); RECOMP_ABI_CALL(0x00054D70u, cRenderStage_SetCustomColorOp_00054D70); /* call 0x00054D70 */

loc_0021DBE5: ;
    PUSH32(esp, 4);
    ecx = 0x3E2200;
    PUSH32(esp, 0x0021DBF1u); RECOMP_ABI_CALL(0x00206A80u, cRenderStage_SetAlphaOp_00206A80); /* call 0x00206A80 */

loc_0021DBF1: ;
    ecx = 0x3E2200;
    PUSH32(esp, 0x0021DBFBu); RECOMP_ABI_CALL(0x00171FE0u, cRenderStage_SetWrapDefault_00171FE0); /* call 0x00171FE0 */

loc_0021DBFB: ;
    PUSH32(esp, 0x10);
    goto loc_0021DC2A;

loc_0021DBFF: ;
    xmm0 = XMM_SCALAR(MEMF(0x361CD0)); /* movss */
    _fca = xmm0.f[0]; _fcb = MEMF(edi + 0x70); /* comiss */
    if ((_fca <= _fcb || _fca != _fca || _fcb != _fcb)) goto loc_0021DC45; /* jbe: below or equal (unsigned <=) (xmm0.f[0] vs MEMF(edi + 0x70)) */

loc_0021DC0D: ;
    eax = MEM32(edi + 0x80);
    PUSH32(esp, eax);
    ecx = 0x3E2190;
    PUSH32(esp, 0x0021DC1Eu); RECOMP_ABI_CALL(0x0002E840u, cRenderStage_SetTexture_0002E840); /* call 0x0002E840 */

loc_0021DC1E: ;
    ecx = 0x3E2190;
    PUSH32(esp, 0x0021DC28u); RECOMP_ABI_CALL(0x00171FE0u, cRenderStage_SetWrapDefault_00171FE0); /* call 0x00171FE0 */

loc_0021DC28: ;
    PUSH32(esp, 0x11);

loc_0021DC2A: ;
    PUSH32(esp, 0x0021DC2Fu); RECOMP_ABI_CALL(0x0020E860u, cShader_GetPixelShaderHandle_0020E860); /* call 0x0020E860 */

loc_0021DC2F: ;
    _fb = (uint32_t)(4) & 0xFFFFFFFFu; _fbs = (int32_t)(int32_t)(_fb); /* add source, before the write */
    esp = esp + 4;
    _fa = (uint32_t)(esp) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* add result */
    PUSH32(esp, eax);
    ecx = 0x4BBCF0;
    PUSH32(esp, 0x0021DC3Du); RECOMP_ABI_CALL(0x00206A10u, cRenderState_SetPixelShader_00206A10); /* call 0x00206A10 */

loc_0021DC3D: ;
    POP32(esp, edi);
    POP32(esp, esi);
    eax = 0; /* xor self */
    _fa = (uint32_t)(eax) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* xor result */
    POP32(esp, ebx);
    esp += 12; return; /* ret 8 */

loc_0021DC45: ;
    _fa = (uint32_t)(MEM32(0x3E21B8)) & 0xFFFFFFFFu; _fb = (uint32_t)(ebx) & 0xFFFFFFFFu;
    _fas = (int32_t)(int32_t)(_fa); _fbs = (int32_t)(int32_t)(_fb); /* cmp MEM32(0x3E21B8), ebx (32-bit) */
    if (CMP_EQ(_fa, _fb)) goto loc_0021DC8A; /* je: equal / zero */

loc_0021DC4D: ;
    ecx = MEM32(0x3E2190);
    PUSH32(esp, ebx);
    PUSH32(esp, ecx);
    PUSH32(esp, 0x0021DC5Au); RECOMP_ABI_CALL(0x002C31C0u, D3DDevice_SetTexture_8_002C31C0); /* call 0x002C31C0 */

loc_0021DC5A: ;
    edx = MEM32(0x491CF8);
    MEM32(0x3E21B8) = ebx;
    eax = MEM32(edx + 4);
    ecx = MEM32(eax + 0x14);
    edx = MEM32(ecx + 0x168);
    eax = MEM32(ecx + 0x164);
    eax = edx + eax + -1;
    edx = ((int32_t)eax < 0) ? 0xFFFFFFFF : 0; /* cdq */
    esi = 0x50;
    { int64_t _dividend = ((int64_t)(int32_t)edx << 32) | eax;
      eax = (uint32_t)((int32_t)(_dividend / (int32_t)esi));
      edx = (uint32_t)((int32_t)(_dividend % (int32_t)esi)); }
    eax = ecx + edx * 4 + 0x24;
    MEM32(eax) = MEM32(eax) + 1;
    _fa = (uint32_t)(MEM32(eax)) & 0xFFFFFFFFu;
    _fas = (int32_t)(int32_t)(_fa); _fb = (_fa == 0x80000000u); /* inc result/SF/OF; CF unchanged */

loc_0021DC8A: ;
    PUSH32(esp, 0xE);
    ecx = 0x3E2190;
    PUSH32(esp, 0x0021DC96u); RECOMP_ABI_CALL(0x00206F60u, cRenderStage_SetColorOp_00206F60); /* call 0x00206F60 */

loc_0021DC96: ;
    PUSH32(esp, 5);
    ecx = 0x3E2190;
    PUSH32(esp, 0x0021DCA2u); RECOMP_ABI_CALL(0x00206A80u, cRenderStage_SetAlphaOp_00206A80); /* call 0x00206A80 */

loc_0021DCA2: ;
    ecx = 0x3E2200;
    PUSH32(esp, 0x0021DCACu); RECOMP_ABI_CALL(0x00054CD0u, cRenderStage_Disable_00054CD0); /* call 0x00054CD0 */

loc_0021DCAC: ;
    POP32(esp, edi);
    POP32(esp, esi);
    eax = 0; /* xor self */
    _fa = (uint32_t)(eax) & 0xFFFFFFFFu; _fas = (int32_t)(int32_t)(_fa); /* xor result */
    POP32(esp, ebx);
    esp += 12; return; /* ret 8 */

}

