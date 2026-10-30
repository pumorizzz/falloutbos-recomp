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
#include <stddef.h>   /* ptrdiff_t */

#include "recomp_types.h"

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

/* Register state comes from recomp_types.h, thread-local as the runtime
 * defines it. A plain `extern uint32_t g_eax` here names a different object. */

/* ---------------------------------------------------------------------------
 * sub_000A4E60 -- Bink's "does this CPU have MMX?" probe, implemented natively.
 *
 * It is the EFLAGS.ID idiom (pushfd / xor 0x200000 / popfd / pushfd) followed
 * by cpuid leaf 1, edx bit 23. All three instructions lift to no-ops on this
 * toolkit version, and a no-op pushfd followed by `pop eax` pops the saved
 * ebx instead, so the probe both answers "no MMX" and corrupts its frame.
 * Bink then has no blitter for the surface format and calls a null pointer.
 *
 * The Xbox CPU is a Coppermine Pentium III, which has MMX, so the answer is
 * fixed. Same effect as the original on that CPU:
 *   [0x000FBC58]  cached result, -1 until probed
 *   [0x0065B67C]  Bink's MMX switch: the cached result, unless the caller
 *                 passed 0x40000 (which turns MMX off -- the original falls
 *                 through to the clear only when that bit is set)
 * cdecl, one argument, returns the cached result in eax.
 *
 * ponytail: game-side because the toolkit fix is community PR #186
 * (pushfd/popfd/cpuid as the hardware does them), not yet merged. Delete
 * this override once a toolkit with it is pinned.
 * ------------------------------------------------------------------------- */
void sub_000A4E60(void)
{
    uint32_t flags = MEM32(g_esp + 4);

    if ((int32_t)MEM32(0x000FBC58u) < 0)
        MEM32(0x000FBC58u) = 1;                  /* P3: MMX present */
    g_eax = MEM32(0x000FBC58u);
    MEM32(0x0065B67Cu) = (g_eax && !(flags & 0x40000u)) ? 1u : 0u;
    g_esp += 4;                                  /* ret */
}

/* ---------------------------------------------------------------------------
 * XAPI media check, sub_00096848 (called directly from 0x0009677E).
 *
 * Two stages:
 *   1. MODE SENSE(10) page 0x3E, the DVD authentication page. The kernel
 *      bridge already answers it as authenticated; this stage passes.
 *   2. Only when the XBE certificate is longer than 0x1D8 bytes and bit 0 of
 *      [cert+0x1D8] is set: READ DVD STRUCTURE of the Xbox security sector
 *      (CDB AD 00 FF 02 FD FF FE 00 06 64 00 C0, 0x664 bytes), validated by
 *      sub_00096791, five attempts. There is no disc to read it from, so it
 *      fails five times and the title exits to the dashboard through
 *      XLaunchNewImage(NULL) / HalReturnToFirmware(2).
 *
 * Some disc revisions carry that certificate bit, some do not; a revision
 * without it boots without ever reaching stage 2. Clearing the bit makes this
 * one take the same path: stage 1, then STATUS_SUCCESS.
 *
 * Done by data rather than by overriding the function: the call is direct,
 * so it does not go through recomp_lookup_manual, and a second definition of
 * sub_00096848 would collide with the generated one. Run once, from the first
 * lookup -- the first indirect call (PsCreateSystemThreadEx) comes long before
 * the check.
 * ------------------------------------------------------------------------- */
static void fbos_skip_dvd_security_sector(void)
{
    static volatile int done;
    uint32_t cert, size, flags;

    if (done)
        return;
    done = 1;

    cert = MEM32(0x00010118u);                   /* XBE header: certificate VA */
    if (!cert)
        return;
    size = MEM32(cert);                          /* certificate size */
    if (size <= 0x1D8u)
        return;                                  /* no such field: stage 2 never runs */

    flags = MEM32(cert + 0x1D8u);
    if (flags & 1u) {
        MEM32(cert + 0x1D8u) = flags & ~1u;
        fprintf(stderr, "[MEDIA] XBE certificate requests the DVD security-sector "
                        "check (size 0x%X, [+0x1D8]=0x%08X); cleared, no disc to read\n",
                size, flags);
        fflush(stderr);
    }
}

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
    fbos_skip_dvd_security_sector();             /* once; before the media check */

    /*
     * TODO: Add your overrides here. Examples:
     *
     * if (xbox_va == 0x00012345) return traced_sub_00012345;
     * if (xbox_va == 0x00067890) return stub_00067890;
     * if (xbox_va == 0x000ABCDE) return fixed_sub_000ABCDE;
     */

    if (xbox_va == 0x000A4E60u) return sub_000A4E60;   /* Bink MMX probe */
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
