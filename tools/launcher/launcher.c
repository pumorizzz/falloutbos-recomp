/*
 * FalloutLauncher.exe: pick the render resolution, the picture size and the
 * anti-aliasing, then start bin\fobos.exe the way Play.cmd does.
 *
 * Everything it sets is an environment variable the game already reads
 * (README, "Settings"): RECOMP_GPU_RASTER_SCALE (the resolution the GPU renders
 * at, a multiple of the game's 640x480), RECOMP_FB_SIZE and
 * RECOMP_FB_FULLSCREEN (the picture), RECOMP_GPU_RASTER_MSAA, RECOMP_FPS_LIMIT
 * (the frame-rate cap). The language copies a set of the game's text files
 * into place (set_language). The choice is
 * kept in bin\launcher.ini. Plain Win32, no resources: built with the game
 * (tools/launcher/CMakeLists.txt) into bin\.
 */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    const char *label;
    const char *value;
} Choice;

/* What the GPU renders at. The game's frame is 640x480; with the 16:9 patch
 * it is anamorphic, so 4x3 is a 2560x1440 16:9 picture pixel for pixel. */
static const Choice k_render[] = {
    { "640 x 480    (the game's own, 1x)", "1" },
    { "1280 x 960   (2x)", "2" },
    { "1920 x 1440  (3x)", "3" },
    { "2560 x 1440  (4x3, sharpest at 1440p)", "4x3" },
    { "2560 x 1920  (4x)", "4" },
};
static const Choice k_output[] = {
    { "1280 x 720", "1280x720" },
    { "1600 x 900", "1600x900" },
    { "1920 x 1080", "1920x1080" },
    { "2560 x 1440", "2560x1440" },
    { "3840 x 2160", "3840x2160" },
};
static const Choice k_aa[] = {
    { "Off", "1" },
    { "MSAA 2x", "2" },
    { "MSAA 4x", "4" },
    { "MSAA 8x", "8" },
};
/* RECOMP_FPS_LIMIT: the flip waits for the next 1/n s, standing in for the
 * TV's vblank. No "unlimited": menus and loading screens would run at
 * hundreds of fps and take a held button as several presses. */
static const Choice k_fps[] = {
    { "30 fps", "30" },
    { "60 fps", "60" },
    { "120 fps", "120" },
};
#define COUNT(a) ((int)(sizeof(a) / sizeof((a)[0])))

/* The game's text: game\resx\<name>.sdb, copied from <name>.sdb.en or .sdb.ru
 * before the start. tools/russian.py apply leaves both sets there (the fonts
 * it patches and its XBE fix suit English too); without it there is no .ru
 * and the choice stays English. */
static const char *const k_sdb[] = { "gtext.sdb", "global.sdb", "deftexte.sdb" };
static const char *const k_lang[] = { "en", "ru" };

enum { ID_RENDER = 100, ID_OUTPUT, ID_AA, ID_FPS, ID_FULL, ID_LANG, ID_PLAY, ID_QUIT };

static char s_root[MAX_PATH];           /* the repository: bin\.. */
static char s_ini[MAX_PATH];
static HWND s_render, s_output, s_aa, s_fps, s_full, s_lang;
static HFONT s_font;

static int find_value(const Choice *c, int n, const char *v, int fallback)
{
    int i;
    for (i = 0; i < n; i++)
        if (strcmp(c[i].value, v) == 0)
            return i;
    return fallback;
}

static HWND make(const char *cls, const char *text, DWORD style, int x, int y, int w,
                 int h, HWND parent, int id)
{
    HWND c = CreateWindowExA(0, cls, text, WS_CHILD | WS_VISIBLE | style, x, y, w, h,
                             parent, (HMENU)(INT_PTR)id, GetModuleHandleA(NULL), NULL);
    SendMessageA(c, WM_SETFONT, (WPARAM)s_font, TRUE);
    return c;
}

static HWND combo(HWND parent, int id, int x, int y, const Choice *c, int n, int sel)
{
    HWND h = make("COMBOBOX", "", CBS_DROPDOWNLIST | WS_TABSTOP | WS_VSCROLL,
                  x, y, 300, 200, parent, id);
    int i;
    for (i = 0; i < n; i++)
        SendMessageA(h, CB_ADDSTRING, 0, (LPARAM)c[i].label);
    SendMessageA(h, CB_SETCURSEL, (WPARAM)sel, 0);
    return h;
}

static int selected(HWND h)
{
    int i = (int)SendMessageA(h, CB_GETCURSEL, 0, 0);
    return i < 0 ? 0 : i;
}

static void save(void)
{
    WritePrivateProfileStringA("launcher", "render", k_render[selected(s_render)].value, s_ini);
    WritePrivateProfileStringA("launcher", "output", k_output[selected(s_output)].value, s_ini);
    WritePrivateProfileStringA("launcher", "msaa", k_aa[selected(s_aa)].value, s_ini);
    WritePrivateProfileStringA("launcher", "fps", k_fps[selected(s_fps)].value, s_ini);
    WritePrivateProfileStringA("launcher", "fullscreen",
        SendMessageA(s_full, BM_GETCHECK, 0, 0) == BST_CHECKED ? "1" : "0", s_ini);
    WritePrivateProfileStringA("launcher", "language", k_lang[selected(s_lang)], s_ini);
}

static int russian_present(void)
{
    char p[MAX_PATH];
    snprintf(p, sizeof p, "%s\\game\\resx\\gtext.sdb.ru", s_root);
    return GetFileAttributesA(p) != INVALID_FILE_ATTRIBUTES;
}

/* src over dst when src is there: 1, unless the copy failed (said why). */
static int copy_set_file(HWND owner, const char *src, const char *dst)
{
    char msg[MAX_PATH + 64];
    if (GetFileAttributesA(src) == INVALID_FILE_ATTRIBUTES)
        return 1;
    if (CopyFileA(src, dst, FALSE))
        return 1;
    snprintf(msg, sizeof msg, "Could not copy %s (error %lu).", src,
             (unsigned long)GetLastError());
    MessageBoxA(owner, msg, "Fallout: Brotherhood of Steel", MB_ICONERROR);
    return 0;
}

/* The whole file, or NULL. */
static unsigned char *read_all(const char *path, DWORD *size)
{
    HANDLE f = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                           FILE_ATTRIBUTE_NORMAL, NULL);
    unsigned char *d = NULL;
    DWORD got = 0;

    if (f == INVALID_HANDLE_VALUE)
        return NULL;
    *size = GetFileSize(f, NULL);
    if (*size != INVALID_FILE_SIZE && (d = (unsigned char *)malloc(*size ? *size : 1)) != NULL
        && (!ReadFile(f, d, *size, &got, NULL) || got != *size)) {
        free(d);
        d = NULL;
    }
    CloseHandle(f);
    return d;
}

static void xbe_error(HWND owner, const char *what)
{
    char msg[512];
    snprintf(msg, sizeof msg, "game\\default.xbe: %s\n\nRun py -3 tools\\russian.py apply again.",
             what);
    MessageBoxA(owner, msg, "Fallout: Brotherhood of Steel", MB_ICONERROR);
}

/* The ten 4-byte code fixes of tools/russian.py (XBE_SITES, keep the two
 * lists alike): the wide sprintf's whole-character copy and nine movsx ->
 * movzx. Without them the Russian strings come out cut to "...". The code
 * that runs is bin\fobos.exe, built from the C generated from default.xbe;
 * regen.sh marks it with how many of the fixes that XBE had (exe_code_fixes).
 * An exe from before the mark leaves only default.xbe to look at: these
 * sites there. widescreen.py does not touch them. */
static const DWORD k_code_va[] = {
    0x00072D46, 0x00014C32, 0x00030560, 0x000306D0, 0x0003B192,
    0x0003B3A1, 0x0003B4A0, 0x0003B501, 0x0004F320, 0x00072AF4,
};

/* File offset of an XBE virtual address (its section headers), or -1. */
static long xbe_offset(const unsigned char *d, DWORD n, DWORD va)
{
    DWORD base, count, at, i;
    if (n < 0x124)
        return -1;
    memcpy(&base, d + 0x104, 4);
    memcpy(&count, d + 0x11C, 4);
    memcpy(&at, d + 0x120, 4);
    for (i = 0; i < count; i++) {
        DWORD h = at - base + i * 56, sva, raw, size;
        if (at < base || h > n || n - h < 20)
            return -1;
        memcpy(&sva, d + h + 4, 4);
        memcpy(&raw, d + h + 12, 4);
        memcpy(&size, d + h + 16, 4);
        if (va >= sva && va - sva < size)
            return raw + (va - sva) <= n ? (long)(raw + (va - sva)) : -1;
    }
    return -1;
}

/* "FBOS-RU-CODE-FIXES n/10" in bin\fobos.exe (tools/russian.py code-mark): n,
 * or -1 for an exe without the mark or one that cannot be read. */
static int exe_code_fixes(void)
{
    static const char tag[] = "FBOS-RU-CODE-FIXES ";
    char p[MAX_PATH];
    unsigned char *d;
    DWORD n = 0, i, len = (DWORD)(sizeof tag - 1);
    int got = -1;

    snprintf(p, sizeof p, "%s\\bin\\fobos.exe", s_root);
    if ((d = read_all(p, &n)) == NULL)
        return -1;
    for (i = 0; n >= len + 5 && i <= n - len - 5; i++)
        if (d[i] == 'F' && memcmp(d + i, tag, len) == 0) {
            char s[8], *e;
            long have;
            memcpy(s, d + i + len, 5);
            s[5] = 0;
            have = strtol(s, &e, 10);
            if (e != s && *e == '/' && strtol(e + 1, NULL, 10) == COUNT(k_code_va))
                got = (int)have;
            break;
        }
    free(d);
    return got;
}

/* The inventory's labels and the loading screen's "Loading..." are 8-bit
 * strings in the XBE's .rdata. default.xbe.en and .ru (tools/russian.py,
 * xbe_variants) differ only in those bytes, so exactly those bytes of
 * default.xbe are set from the chosen one. The rest of the file -- the code
 * the C was generated from, 16:9 or 4:3 (widescreen.py) -- stays as it is:
 * copying the whole variant put back the XBE of the last `russian.py apply`
 * and undid a later widescreen.py apply or revert. 1, or 0 after saying why. */
static int set_xbe_strings(HWND owner, const char *lang)
{
    char cur_p[MAX_PATH], en_p[MAX_PATH], ru_p[MAX_PATH], tmp_p[MAX_PATH];
    unsigned char *cur, *en, *ru, *want;
    DWORD n_cur = 0, n_en = 0, n_ru = 0, i, changed = 0;
    int ok = 0, fixes;

    snprintf(cur_p, sizeof cur_p, "%s\\game\\default.xbe", s_root);
    snprintf(en_p, sizeof en_p, "%s.en", cur_p);
    snprintf(ru_p, sizeof ru_p, "%s.ru", cur_p);
    if (GetFileAttributesA(en_p) == INVALID_FILE_ATTRIBUTES ||
        GetFileAttributesA(ru_p) == INVALID_FILE_ATTRIBUTES)
        return 1;                       /* no russian.py apply: nothing to set */
    cur = read_all(cur_p, &n_cur);
    en = read_all(en_p, &n_en);
    ru = read_all(ru_p, &n_ru);
    want = strcmp(lang, "ru") == 0 ? ru : en;
    if (!cur || !en || !ru) {
        xbe_error(owner, "could not read it or its .en/.ru set.");
        goto out;
    }
    if (n_cur != n_en || n_en != n_ru) {
        xbe_error(owner, "it is not the image its .en/.ru set was made from.");
        goto out;
    }
    /* Russian needs the code fixes in the game; English is the original. */
    if (want == ru && (fixes = exe_code_fixes()) >= 0) {
        if (fixes != COUNT(k_code_va)) {
            MessageBoxA(owner, "bin\\fobos.exe was built from a default.xbe without the code "
                               "fixes of tools\\russian.py, and the Russian text would come out "
                               "cut to \"...\". Run\n\n"
                               "py -3 tools\\russian.py apply\n./regen.sh\n"
                               "cmake --build build-msvc --config Release",
                        "Fallout: Brotherhood of Steel", MB_ICONERROR);
            goto out;
        }
    } else if (want == ru)
        for (i = 0; i < (DWORD)COUNT(k_code_va); i++) {
            long o = xbe_offset(cur, n_cur, k_code_va[i]);
            if (o < 0 || (DWORD)o + 4 > n_cur || memcmp(cur + o, en + o, 4) != 0) {
                xbe_error(owner, "it lacks the code fixes of tools\\russian.py "
                                 "(unpacked from the disc again?).");
                goto out;
            }
        }
    for (i = 0; i < n_cur; i++)
        if (en[i] != ru[i] && cur[i] != en[i] && cur[i] != ru[i]) {
            xbe_error(owner, "its strings are neither the English nor the Russian ones.");
            goto out;
        }
    for (i = 0; i < n_cur; i++)
        if (en[i] != ru[i] && cur[i] != want[i]) {
            cur[i] = want[i];
            changed++;
        }
    if (changed) {
        /* Written beside it and moved over, so a failed write never leaves a
         * half-written XBE. */
        HANDLE f;
        DWORD put = 0;
        snprintf(tmp_p, sizeof tmp_p, "%s.tmp", cur_p);
        f = CreateFileA(tmp_p, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        if (f == INVALID_HANDLE_VALUE || !WriteFile(f, cur, n_cur, &put, NULL) || put != n_cur
            || !FlushFileBuffers(f)) {
            char what[96];
            snprintf(what, sizeof what, "could not write it (error %lu).",
                     (unsigned long)GetLastError());
            if (f != INVALID_HANDLE_VALUE)
                CloseHandle(f);
            DeleteFileA(tmp_p);
            xbe_error(owner, what);
            goto out;
        }
        CloseHandle(f);
        if (!MoveFileExA(tmp_p, cur_p, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
            char what[96];
            snprintf(what, sizeof what, "could not replace it (error %lu); is the game running?",
                     (unsigned long)GetLastError());
            DeleteFileA(tmp_p);
            xbe_error(owner, what);
            goto out;
        }
    }
    ok = 1;
out:
    free(cur);
    free(en);
    free(ru);
    return ok;
}

/* Copy the chosen language's .sdb set into place, and set the XBE's strings.
 * A set that is not there (no tools/russian.py apply yet, so no .en either)
 * leaves the files as they are: 1, unless a copy failed. */
static int set_language(HWND owner)
{
    const char *lang = k_lang[selected(s_lang)];
    char src[MAX_PATH], dst[MAX_PATH];
    int i;

    if (strcmp(lang, "ru") == 0 && !russian_present()) {
        MessageBoxA(owner, "The Russian text is not installed: run\n"
                           "py -3 tools\\russian.py apply", "Fallout: Brotherhood of Steel",
                    MB_ICONERROR);
        return 0;
    }
    if (!set_xbe_strings(owner, lang))
        return 0;
    for (i = 0; i < COUNT(k_sdb); i++) {
        snprintf(src, sizeof src, "%s\\game\\resx\\%s.%s", s_root, k_sdb[i], lang);
        snprintf(dst, sizeof dst, "%s\\game\\resx\\%s", s_root, k_sdb[i]);
        if (!copy_set_file(owner, src, dst))
            return 0;
    }
    /* Each level's own names: game\resx\c<n>\<LEVEL>\<LEVEL>.sdb */
    {
        char pat[MAX_PATH];
        WIN32_FIND_DATAA c, l;
        HANDLE hc, hl;
        snprintf(pat, sizeof pat, "%s\\game\\resx\\c?", s_root);
        hc = FindFirstFileA(pat, &c);
        if (hc != INVALID_HANDLE_VALUE) {
            do {
                if (!(c.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY))
                    continue;
                snprintf(pat, sizeof pat, "%s\\game\\resx\\%s\\*", s_root, c.cFileName);
                hl = FindFirstFileA(pat, &l);
                if (hl == INVALID_HANDLE_VALUE)
                    continue;
                do {
                    if (!(l.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) || l.cFileName[0] == '.')
                        continue;
                    snprintf(dst, sizeof dst, "%s\\game\\resx\\%s\\%s\\%s.sdb", s_root,
                             c.cFileName, l.cFileName, l.cFileName);
                    snprintf(src, sizeof src, "%s.%s", dst, lang);
                    if (!copy_set_file(owner, src, dst)) {
                        FindClose(hl);
                        FindClose(hc);
                        return 0;
                    }
                } while (FindNextFileA(hl, &l));
                FindClose(hl);
            } while (FindNextFileA(hc, &c));
            FindClose(hc);
        }
    }
    return 1;
}

/* bin\fobos.exe, from the repository root (it reads game\default.xbe), with
 * what Play.cmd sets plus the choice. 0 on failure, after saying why.
 *
 * Its output goes to fobos.log in the root, with no console window. The
 * runtime prints a report every ten seconds from the thread that runs the
 * pushbuffer; into a console that took 20-40 ms and showed as a hitch every
 * ten seconds, into a file it takes 2-3. */
static int play(HWND owner)
{
    char exe[MAX_PATH], cmd[MAX_PATH + 2], log[MAX_PATH];
    STARTUPINFOA si;
    PROCESS_INFORMATION pi;
    SECURITY_ATTRIBUTES sa;
    HANDLE out;
    BOOL ok;

    snprintf(exe, sizeof exe, "%s\\bin\\fobos.exe", s_root);
    if (GetFileAttributesA(exe) == INVALID_FILE_ATTRIBUTES) {
        MessageBoxA(owner, "bin\\fobos.exe is not built yet. Run Setup.cmd first.",
                    "Fallout: Brotherhood of Steel", MB_ICONERROR);
        return 0;
    }
    SetEnvironmentVariableA("RECOMP_PB_EXEC", "1");
    SetEnvironmentVariableA("RECOMP_FB_WINDOW", "1");
    SetEnvironmentVariableA("RECOMP_KEYBOARD", "1");
    /* As Play.cmd: RECOMP_GPU_RASTER=0 set beforehand keeps the CPU rasteriser. */
    if (GetEnvironmentVariableA("RECOMP_GPU_RASTER", NULL, 0) == 0)
        SetEnvironmentVariableA("RECOMP_GPU_RASTER", "1");
    SetEnvironmentVariableA("RECOMP_PAD_RECORD", "saves\\pad_path.txt");
    SetEnvironmentVariableA("RECOMP_GPU_RASTER_SCALE", k_render[selected(s_render)].value);
    SetEnvironmentVariableA("RECOMP_GPU_RASTER_MSAA", k_aa[selected(s_aa)].value);
    SetEnvironmentVariableA("RECOMP_FB_SIZE", k_output[selected(s_output)].value);
    SetEnvironmentVariableA("RECOMP_FPS_LIMIT", k_fps[selected(s_fps)].value);
    SetEnvironmentVariableA("RECOMP_FB_FULLSCREEN",
        SendMessageA(s_full, BM_GETCHECK, 0, 0) == BST_CHECKED ? "1" : "0");
    memset(&sa, 0, sizeof sa);
    sa.nLength = sizeof sa;
    sa.bInheritHandle = TRUE;
    snprintf(log, sizeof log, "%s\\fobos.log", s_root);
    out = CreateFileA(log, GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, &sa,
                      CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    memset(&si, 0, sizeof si);
    si.cb = sizeof si;
    if (out != INVALID_HANDLE_VALUE) {
        si.dwFlags = STARTF_USESTDHANDLES;
        si.hStdInput = NULL;
        si.hStdOutput = out;
        si.hStdError = out;
    }
    snprintf(cmd, sizeof cmd, "\"%s\"", exe);
    ok = CreateProcessA(exe, cmd, NULL, NULL, out != INVALID_HANDLE_VALUE,
                        CREATE_NO_WINDOW, NULL, s_root, &si, &pi);
    if (out != INVALID_HANDLE_VALUE)
        CloseHandle(out);
    if (!ok) {
        char msg[128];
        snprintf(msg, sizeof msg, "Could not start bin\\fobos.exe (error %lu).",
                 (unsigned long)GetLastError());
        MessageBoxA(owner, msg, "Fallout: Brotherhood of Steel", MB_ICONERROR);
        return 0;
    }
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return 1;
}

static LRESULT CALLBACK wndproc(HWND h, UINT m, WPARAM w, LPARAM l)
{
    switch (m) {
    case WM_CREATE: {
        char v[32];
        int y = 16;
        make("STATIC", "Render resolution (the GPU draws at):", 0, 16, y, 300, 18, h, 0);
        GetPrivateProfileStringA("launcher", "render", "3", v, sizeof v, s_ini);
        s_render = combo(h, ID_RENDER, 16, y + 20, k_render, COUNT(k_render),
                         find_value(k_render, COUNT(k_render), v, 2));
        y += 56;
        make("STATIC", "Output (the picture's size):", 0, 16, y, 300, 18, h, 0);
        GetPrivateProfileStringA("launcher", "output", "2560x1440", v, sizeof v, s_ini);
        s_output = combo(h, ID_OUTPUT, 16, y + 20, k_output, COUNT(k_output),
                         find_value(k_output, COUNT(k_output), v, 3));
        s_full = make("BUTTON", "Borderless full screen (F11 in game)",
                      BS_AUTOCHECKBOX | WS_TABSTOP, 16, y + 50, 300, 20, h, ID_FULL);
        if (GetPrivateProfileIntA("launcher", "fullscreen", 1, s_ini))
            SendMessageA(s_full, BM_SETCHECK, BST_CHECKED, 0);
        y += 84;
        make("STATIC", "Anti-aliasing:", 0, 16, y, 300, 18, h, 0);
        GetPrivateProfileStringA("launcher", "msaa", "4", v, sizeof v, s_ini);
        s_aa = combo(h, ID_AA, 16, y + 20, k_aa, COUNT(k_aa),
                     find_value(k_aa, COUNT(k_aa), v, 2));
        y += 56;
        make("STATIC", "Frame rate limit:", 0, 16, y, 300, 18, h, 0);
        GetPrivateProfileStringA("launcher", "fps", "60", v, sizeof v, s_ini);
        s_fps = combo(h, ID_FPS, 16, y + 20, k_fps, COUNT(k_fps),
                      find_value(k_fps, COUNT(k_fps), v, 1));
        y += 56;
        make("STATIC", "Language:", 0, 16, y, 300, 18, h, 0);
        /* A Unicode combo of its own, so "Русский" shows under any code page. */
        s_lang = CreateWindowExW(0, L"COMBOBOX", L"",
                                 WS_CHILD | WS_VISIBLE | CBS_DROPDOWNLIST | WS_TABSTOP,
                                 16, y + 20, 300, 200, h, (HMENU)(INT_PTR)ID_LANG,
                                 GetModuleHandleA(NULL), NULL);
        SendMessageW(s_lang, WM_SETFONT, (WPARAM)s_font, TRUE);
        SendMessageW(s_lang, CB_ADDSTRING, 0, (LPARAM)L"English (original)");
        SendMessageW(s_lang, CB_ADDSTRING, 0,
                     (LPARAM)L"\x0420\x0443\x0441\x0441\x043a\x0438\x0439 (Russian)");
        /* The original language until the player picks another. */
        GetPrivateProfileStringA("launcher", "language", "en", v, sizeof v, s_ini);
        SendMessageW(s_lang, CB_SETCURSEL, strcmp(v, "ru") == 0 ? 1 : 0, 0);
        y += 60;
        make("STATIC", "Higher render resolution and MSAA cost GPU time;\n"
                       "3x with MSAA 4x holds 60 fps on a fast card.",
             0, 16, y, 300, 34, h, 0);
        y += 44;
        make("BUTTON", "Play", BS_DEFPUSHBUTTON | WS_TABSTOP, 136, y, 86, 28, h, ID_PLAY);
        make("BUTTON", "Quit", BS_PUSHBUTTON | WS_TABSTOP, 230, y, 86, 28, h, ID_QUIT);
        return 0;
    }
    case WM_COMMAND:
        if (LOWORD(w) == ID_PLAY) {
            save();
            if (set_language(h) && play(h))
                DestroyWindow(h);
        } else if (LOWORD(w) == ID_QUIT) {
            DestroyWindow(h);
        }
        return 0;
    case WM_CTLCOLORSTATIC:
        SetBkMode((HDC)w, TRANSPARENT);
        return (LRESULT)GetSysColorBrush(COLOR_BTNFACE);
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcA(h, m, w, l);
}

int WINAPI WinMain(HINSTANCE inst, HINSTANCE prev, LPSTR cmdline, int show)
{
    WNDCLASSA wc;
    NONCLIENTMETRICSA ncm;
    RECT r = { 0, 0, 332, 464 };
    MSG msg;
    HWND h;
    char *slash;

    (void)prev; (void)cmdline;
    SetProcessDPIAware();
    /* The launcher sits in bin\; the game runs from the folder above it. */
    GetModuleFileNameA(NULL, s_root, sizeof s_root);
    if ((slash = strrchr(s_root, '\\')) != NULL)
        *slash = 0;
    snprintf(s_ini, sizeof s_ini, "%s\\launcher.ini", s_root);
    if ((slash = strrchr(s_root, '\\')) != NULL && _stricmp(slash + 1, "bin") == 0)
        *slash = 0;

    ncm.cbSize = sizeof ncm;
    if (SystemParametersInfoA(SPI_GETNONCLIENTMETRICS, sizeof ncm, &ncm, 0))
        s_font = CreateFontIndirectA(&ncm.lfMessageFont);
    else
        s_font = (HFONT)GetStockObject(DEFAULT_GUI_FONT);

    memset(&wc, 0, sizeof wc);
    wc.lpfnWndProc = wndproc;
    wc.hInstance = inst;
    wc.hCursor = LoadCursorA(NULL, IDC_ARROW);
    wc.hIcon = LoadIconA(NULL, IDI_APPLICATION);
    wc.hbrBackground = GetSysColorBrush(COLOR_BTNFACE);
    wc.lpszClassName = "FbosLauncher";
    RegisterClassA(&wc);
    AdjustWindowRect(&r, WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX, FALSE);
    h = CreateWindowExA(0, wc.lpszClassName, "Fallout: Brotherhood of Steel",
                        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
                        CW_USEDEFAULT, CW_USEDEFAULT, r.right - r.left, r.bottom - r.top,
                        NULL, NULL, inst, NULL);
    if (!h)
        return 1;
    ShowWindow(h, show);
    UpdateWindow(h);
    while (GetMessageA(&msg, NULL, 0, 0) > 0) {
        if (!IsDialogMessageA(h, &msg)) {
            TranslateMessage(&msg);
            DispatchMessageA(&msg);
        }
    }
    return 0;
}
