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
#include <stdlib.h>   /* getenv, atoi */
#include <time.h>     /* time */
#include <stddef.h>   /* ptrdiff_t */
#include <string.h>

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
 * sub_00096848 would collide with the generated one. Run once from main(), after
 * the image is mapped and before the entry point: it used to run from the first
 * recomp_lookup_manual, which worked only because the first indirect call comes
 * long before the check.
 * ------------------------------------------------------------------------- */
void fbos_skip_dvd_security_sector(void)
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

/* ---------------------------------------------------------------------------
 * Movie subtitles (Russian), drawn over a Bink movie in the game's own font.
 *
 * The movie player keeps the playing file's path at 0x29A1C0 and its Bink
 * handle at [0x29A234] (+0x0C current frame, 1-based; +0x14/+0x18 frame rate
 * and divisor). Each frame the main loop (0x90170) draws the movie (0x78F10),
 * then calls sub_0003A250, then 0x8F330, which draws the queued 8-bit text
 * over everything and presents. So the subtitle is queued in sub_0003A250,
 * the way the credits queue theirs (0x43710): 0x712C0 opens a block in a
 * font and colour, 0x71A70 queues a line centred on x (the queue copies the
 * string), 0x71380 closes it.
 *
 * The cues come from the game's own text: gtext.sdb of the Russian set has
 * one string per movie under the key "SUB_<movie>" (tools/russian.py, from
 * tools/ru/movies.tsv), looked up through 0x5AA00 like any other key. A line
 * a cue, "<start> <end> <text>" in seconds, '^' a line break, the text in the
 * cp1251 code points the fonts draw. The English set has no such key: English
 * plays without subtitles, and the launcher's language switch needs nothing.
 * ------------------------------------------------------------------------- */
extern void sub_0005AA00(void);
extern void sub_000712C0(void);
extern void sub_00071310(void);
extern void sub_00071380(void);
extern void sub_00071A70(void);
extern void sub_00019820(void);

#define SUB_MAX_CUES 48
#define SUB_TEXT     192

static struct {
    char movie[96];                     /* path the cues below are for */
    int  count;                         /* -1 lookup not done, 0 none */
    struct { float a, b; char text[SUB_TEXT]; } cue[SUB_MAX_CUES];
} s_sub = { "", -1 };

/* The game's key hash (0x1E1F0, the same for .clp names). */
static uint32_t fbos_key_hash(const char *s)
{
    uint32_t h = 0;
    for (; *s; s++) {
        int c = (signed char)(*s == '\\' ? '/' : *s);
        h = ((h * 0x80000025u) ^ (h >> 27)) ^ (uint32_t)c;
    }
    return h;
}

/* Call a game function: args pushed right to left and `from` as the return
 * address -- the replaced function this stands in for, so a fault's backtrace
 * names it; esp comes back to where it was whichever convention the callee has
 * (cdecl or stdcall). eax comes back. */
static uint32_t fbos_guest_call(void (*fn)(void), const uint32_t *args, int n, uint32_t from)
{
    uint32_t sp = g_esp, ebx = g_ebx, esi = g_esi, edi = g_edi, ebp = g_ebp;
    int i;
    for (i = n - 1; i >= 0; i--)
        PUSH32(g_esp, args[i]);
    PUSH32(g_esp, from);
    fn();
    g_esp = sp;                                 /* both conventions: back to before */
    g_ebx = ebx; g_esi = esi; g_edi = edi; g_ebp = ebp;
    return g_eax;
}

/* "intro" from "d:\resx\intro.bik", lower case. */
static void fbos_sub_key(const char *path, char *out, size_t size)
{
    const char *b = path, *p;
    size_t n = 0;
    for (p = path; *p; p++)
        if (*p == '\\' || *p == '/' || *p == ':')
            b = p + 1;
    n = (size_t)snprintf(out, size, "SUB_");
    for (p = b; *p && *p != '.' && n + 1 < size; p++)
        out[n++] = (char)((*p >= 'A' && *p <= 'Z') ? *p - 'A' + 'a' : *p);
    out[n] = 0;
}

static void fbos_sub_load(const char *path)
{
    char key[64];
    uint32_t h, s, n = 0, i;
    char line[SUB_TEXT + 32];

    snprintf(s_sub.movie, sizeof s_sub.movie, "%s", path);
    s_sub.count = 0;
    fbos_sub_key(path, key, sizeof key);
    h = fbos_key_hash(key);
    s = fbos_guest_call(sub_0005AA00, &h, 1, 0x0003A250u);   /* wide string or 0 */
    fprintf(stderr, "[SUB] movie %s: %s\n", key, s ? "subtitles" : "none");
    if (!s)
        return;
    for (i = 0;; i += 2) {
        uint16_t c = MEM16(s + i);
        if (c == 0 || c == '\n') {
            float a, b;
            int off = 0;
            line[n] = 0;
            if (n && sscanf(line, "%f %f %n", &a, &b, &off) == 2 && off
                && s_sub.count < SUB_MAX_CUES) {
                s_sub.cue[s_sub.count].a = a;
                s_sub.cue[s_sub.count].b = b;
                snprintf(s_sub.cue[s_sub.count].text, SUB_TEXT, "%s", line + off);
                s_sub.count++;
            }
            n = 0;
            if (c == 0)
                break;
        } else if (n + 1 < sizeof line) {
            line[n++] = (char)(c & 0xFF);        /* cp1251 code points: one byte each */
        }
    }
}

static void fbos_subtitles(void)
{
    uint32_t bink = MEM32(0x0029A234u), frame, rate, div, i;
    const char *path = (const char *)XBOX_PTR(0x0029A1C0u);
    float t;

    if (!bink || !path[0])
        return;
    if (s_sub.count < 0 || strcmp(s_sub.movie, path) != 0)
        fbos_sub_load(path);
    if (s_sub.count <= 0)
        return;
    frame = MEM32(bink + 0x0C);
    rate = MEM32(bink + 0x14);
    div = MEM32(bink + 0x18);
    if (!rate || !div || !frame)
        return;
    t = (float)(frame - 1) * (float)div / (float)rate;
    for (i = 0; i < (uint32_t)s_sub.count; i++)
        if (t >= s_sub.cue[i].a && t < s_sub.cue[i].b)
            break;
    if (i == (uint32_t)s_sub.count)
        return;
    {
        /* Lines bottom-up from y 416, 20 apart (gamefonta, 18 px): lower,
         * the 16:9 picture's bottom bar covered the last line. */
        const char *txt = s_sub.cue[i].text;
        const char *line[4];
        int nl = 0, k;
        uint32_t eax = g_eax, ecx = g_ecx, edx = g_edx;
        uint32_t args[4];

        line[nl++] = txt;
        for (; *txt && nl < 4; txt++)
            if (*txt == '^')
                line[nl++] = txt + 1;
        args[0] = MEM32(0x001CC5FCu);            /* gamefonta */
        args[1] = 7; args[2] = 1; args[3] = 0xFFFFFFFFu;
        fbos_guest_call(sub_000712C0, args, 4, 0x0003A250u);
        args[0] = 0xFFFFFFFFu;                   /* opaque white */
        fbos_guest_call(sub_00071310, args, 1, 0x0003A250u);
        for (k = 0; k < nl; k++) {
            const char *e = strchr(line[k], '^');
            size_t len = e ? (size_t)(e - line[k]) : strlen(line[k]);
            uint32_t buf, j;
            /* The string on the guest stack: the queue copies it. */
            g_esp -= 256;
            buf = g_esp;
            for (j = 0; j < len && j < 255; j++)
                MEM8(buf + j) = (uint8_t)line[k][j];
            MEM8(buf + j) = 0;
            args[0] = 320;
            args[1] = (uint32_t)(416 - (nl - 1 - k) * 20);
            args[2] = buf;
            fbos_guest_call(sub_00071A70, args, 3, 0x0003A250u);
            g_esp += 256;
        }
        fbos_guest_call(sub_00071380, args, 0, 0x0003A250u);
        g_eax = eax; g_ecx = ecx; g_edx = edx;
    }
}

/* FBOS_TEST_LEVELUP=<seconds>, a test switch: raise player 1's "level
 * gained" flag (bit 0 of [player+0x828], set by sub_00036250 when experience
 * crosses a level) that many seconds after each new player object appears,
 * so the HUD shows "Press BACK to Level Up" without playing to the next
 * level. Player 1 is [0x10D0CC]. The HUD (sub_000414F0) starts a 4-second
 * timer at [hud+0xC0] when it first sees the flag and sub_00041B40 draws the
 * prompt while it runs, as after a real level-up: hence the delay, to get
 * past a level's opening window first. Only the flag: the level-up screen it
 * opens gives no points that experience did not earn. */
static void fbos_test_levelup(void)
{
    static int delay = -2;
    static uint32_t seen, done;
    static time_t t0;
    uint32_t p;

    if (delay == -2) {
        const char *v = getenv("FBOS_TEST_LEVELUP");
        delay = v && *v ? atoi(v) : -1;
        if (delay >= 0)
            fprintf(stderr, "[TEST] FBOS_TEST_LEVELUP: level-up flag on player 1 after %d s\n", delay);
    }
    if (delay < 0)
        return;
    p = MEM32(0x0010D0CCu);
    if (!p || p == done)
        return;
    if (p != seen) {
        seen = p;
        t0 = time(NULL);
    }
    if (time(NULL) - t0 >= delay) {
        MEM32(p + 0x828) |= 1;
        done = p;
        fprintf(stderr, "[TEST] level-up flag set on player 0x%08X\n", p);
    }
}

/* sub_0003A250, as the original (each object on the list at [0x10E1EC] gets
 * vtable[0](1), then a tail jump to 0x19820 with ecx = 0x10E1EC), with the
 * movie subtitle queued first. Called once a frame from the main loop. */
#define eax g_eax
void sub_0003A250(void)
{
    uint32_t node;

    fbos_test_levelup();
    fbos_subtitles();
    PUSH32(g_esp, g_esi);
    for (node = MEM32(0x0010E1ECu); node; node = MEM32(node + 4)) {
        uint32_t obj = MEM32(node);
        if (!obj)
            continue;
        g_esi = node;
        g_ecx = obj;
        g_eax = MEM32(obj);
        {
            uint32_t _icall_esp = g_esp;
            PUSH32(g_esp, 1);
            PUSH32(g_esp, 0x0003A26Cu);
            RECOMP_ICALL_SAFE_AT(MEM32(g_eax), _icall_esp, 0x0003A26Au);
        }
        node = g_esi;
    }
    g_ecx = 0x0010E1ECu;
    POP32(g_esp, g_esi);
    sub_00019820();                               /* tail jmp 0x19820 */
}
#undef eax

/* ---------------------------------------------------------------------------
 * The trailer in the Extras menu.
 *
 * The movie table (.data 0xED1F8 + n*0x100, a path each) holds 17 movies;
 * the one to play is the number in [0xFA398] (0x6A80F opens it). Number 0 is
 * FO_Trailer.bik, and nothing in the game ever stores 0 there: the trailer is
 * on the disc but unreachable. The Extras menu (vtable 0xE3B40) builds its
 * list in sub_000447D0 (an item per gtext key, by unlock level [0x276FCC]) and
 * on a choice sub_000449B0 maps the item's key to a movie number; a key it
 * does not know falls through to "play [0xFA398]".
 *
 * So: the list gets a "Trailer" item after "Fallout Intro" when gtext has the
 * key BONUS_TRAILER (tools/russian.py adds it to the Russian set; the English
 * set has none, and English keeps the original list), and choosing it stores
 * 0 before the original handler runs.
 *
 * fo1_intro.bik (Fallout 1's intro, with the GNN card) is on the disc too but
 * not even in the table, and the table cannot grow (the credits table follows
 * at 0xEE300). Movie 0's slot is used by nothing else, so the choice hook
 * writes the chosen movie's path into it: "Fallout 1 Intro" (key
 * BONUS_FO1_INTRO) plays through slot 0 as well, and so do the other files
 * nothing names: the nuclear-test reel (NuclearBlast.bik, the same file as
 * MainMenu.bik) and the other Skinlab cut (New_Bonus_SkinLab.bik).
 * ------------------------------------------------------------------------- */
extern void sub_0005B1B0(void);
extern void sub_0005B1F0(void);
extern void sub_0005B280(void);
extern void sub_0005B520(void);
extern void sub_000729A0(void);

#define BONUS_SLOT0       0x000ED1F8u             /* movie 0's path, 0x100 bytes */

/* The movies the port adds, each shown when gtext has its key. Every key
 * falls through the handler's switch to "play [0xFA398]" (checked by hash). */
static const struct { uint32_t key; const char *path; } bonus_movies[] = {
    { 0x637370ACu, "d:\\resx\\FO_Trailer.bik" },  /* BONUS_TRAILER: the trailer */
    { 0xC8441180u, "d:\\resx\\fo1_intro.bik" },   /* BONUS_FO1_INTRO: Fallout 1's intro */
    { 0xEFC0C541u, "d:\\resx\\NuclearBlast.bik" },/* BONUS_NUKE: the nuclear-test reel */
    { 0x09F77C95u, "d:\\resx\\New_Bonus_SkinLab.bik" }, /* BONUS_SKINLAB2: the other Skinlab cut */
};

static uint32_t bonus_this_call(void (*fn)(void), uint32_t self, const uint32_t *args, int n,
                                uint32_t from)
{
    g_ecx = self;
    return fbos_guest_call(fn, args, n, from);
}

/* The helpers below are the Extras list's (the replaced function at 0x447D0). */
static uint32_t bonus_text(uint32_t key)
{
    g_ecx = MEM32(0x00114850u);
    return fbos_guest_call(sub_0005AA00, &key, 1, 0x000447D0u);    /* wide string or 0 */
}

static void bonus_add(uint32_t self, uint32_t key)
{
    uint32_t args[5] = { key, 0, 1, key, 0 };
    bonus_this_call(sub_0005B1B0, self, args, 5, 0x000447D0u);
}

/* An added movie's item, if gtext has its key. */
static void bonus_add_movie(uint32_t self, int n)
{
    if (bonus_text(bonus_movies[n].key))
        bonus_add(self, bonus_movies[n].key);
}

/* sub_000447D0, thiscall (1 argument, ret 4): the Extras list, as the
 * original, with the added movies' items. */
void sub_000447D0(void)
{
    static const uint32_t level6[] = {
        0xC2846018u, 0xC9DA1D98u, 0xC9DA1D99u, 0xC9DA1D9Au,
        0xC9DA1D9Bu, 0xC9DA1D9Cu, 0xC9DA1D9Du,
    };
    uint32_t self = g_ecx, arg = MEM32(g_esp + 4), args[6], s, i;
    int32_t level;
    float f;

    args[0] = arg; args[1] = 0;
    bonus_this_call(sub_0005B1F0, self, args, 2, 0x000447D0u);
    MEM8(self + 0x80) = 0;
    MEM16(self + 0x82) = 0;
    MEM32(self) = 0x000E3B40u;
    MEM8(self + 0x62) = 4;

    bonus_add(self, 0xC2846013u);                 /* Fallout Intro */
    bonus_add_movie(self, 0);                     /* Trailer */
    bonus_add_movie(self, 1);                     /* Fallout 1 Intro */
    bonus_add_movie(self, 2);                     /* Nuclear reel */
    bonus_add(self, 0xC2846012u);                 /* Credits */
    bonus_add(self, 0xC2846015u);                 /* Chapter 1 - Cain */
    bonus_add(self, 0xC2846014u);                 /* Chapter 1 - Cyrus */
    bonus_add(self, 0xC2846017u);                 /* Chapter 1 - Nadia */
    level = (int32_t)MEM32(0x00276FCCu);
    if (level >= 4)
        bonus_add(self, 0xC2846016u);             /* Chapter 2 */
    if (level >= 5)
        bonus_add(self, 0xC2846019u);             /* Chapter 3 */
    if (level >= 6) {
        for (i = 0; i < sizeof level6 / sizeof level6[0]; i++)
            bonus_add(self, level6[i]);           /* Mutant Transformation .. Skinlab */
        bonus_add_movie(self, 3);                 /* the other Skinlab cut */
    }

    /* The title: wide sprintf(this + 0x82, text 0x901D09A6, (float)[0x277300],
     * (float)[0x2771C8], 0, 0), then select with -1. */
    s = bonus_text(0x901D09A6u);
    args[0] = self + 0x82;
    args[1] = s;
    f = (float)(int32_t)MEM32(0x00277300u); memcpy(&args[2], &f, 4);
    f = (float)(int32_t)MEM32(0x002771C8u); memcpy(&args[3], &f, 4);
    args[4] = 0; args[5] = 0;
    fbos_guest_call(sub_000729A0, args, 6, 0x000447D0u);
    args[0] = 0xFFFFFFFFu;
    bonus_this_call(sub_0005B520, self, args, 1, 0x000447D0u);

    g_eax = self;
    g_esp += 8;                                   /* ret 4 */
}

static void bonus_slot0(const char *path)
{
    uint32_t i;
    for (i = 0; i < 0x100; i++) {
        MEM8(BONUS_SLOT0 + i) = (uint8_t)*path;
        if (*path)
            path++;
    }
}

/* Entry hook of sub_000449B0 (the Extras choice, thiscall): the chosen item
 * is sub_0005B280((char)[this+0x60], -1); for an added item put its movie in
 * slot 0 and store movie 0, which the original then plays through its
 * default branch. */
void sub_000449B0_enter(void)
{
    uint32_t self = g_ecx, eax = g_eax, edx = g_edx, args[2], item, key, i;

    args[0] = (uint32_t)(int32_t)(int8_t)MEM8(self + 0x60);
    args[1] = 0xFFFFFFFFu;
    item = bonus_this_call(sub_0005B280, self, args, 2, 0x000449B0u);
    key = item ? MEM32(item + 0x70) : 0;
    for (i = 0; i < sizeof bonus_movies / sizeof bonus_movies[0]; i++)
        if (key == bonus_movies[i].key) {
            bonus_slot0(bonus_movies[i].path);
            MEM32(0x000FA398u) = 0;
        }
    g_ecx = self; g_eax = eax; g_edx = edx;
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
