/*
 * FalloutLauncher.exe: pick the render resolution, the picture size and the
 * anti-aliasing, then start bin\fbos.exe the way Play.cmd does.
 *
 * Everything it sets is an environment variable the game already reads
 * (README, "Usage"): RECOMP_GPU_RASTER_SCALE (the resolution the GPU renders
 * at, a multiple of the game's 640x480), RECOMP_FB_SIZE and
 * RECOMP_FB_FULLSCREEN (the picture), RECOMP_GPU_RASTER_MSAA, RECOMP_FPS_LIMIT
 * (the frame-rate cap). The choice is
 * kept in bin\launcher.ini. Plain Win32, no resources: built with the game
 * (tools/launcher/CMakeLists.txt) into bin\.
 */
#include <windows.h>
#include <stdio.h>
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

enum { ID_RENDER = 100, ID_OUTPUT, ID_AA, ID_FPS, ID_FULL, ID_PLAY, ID_QUIT };

static char s_root[MAX_PATH];           /* the repository: bin\.. */
static char s_ini[MAX_PATH];
static HWND s_render, s_output, s_aa, s_fps, s_full;
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
}

/* bin\fbos.exe, from the repository root (it reads game\default.xbe), with
 * what Play.cmd sets plus the choice. 0 on failure, after saying why.
 *
 * Its output goes to fbos.log in the root, with no console window. The
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

    snprintf(exe, sizeof exe, "%s\\bin\\fbos.exe", s_root);
    if (GetFileAttributesA(exe) == INVALID_FILE_ATTRIBUTES) {
        MessageBoxA(owner, "bin\\fbos.exe is not built yet. Run Setup.cmd first.",
                    "Fallout: Brotherhood of Steel", MB_ICONERROR);
        return 0;
    }
    SetEnvironmentVariableA("RECOMP_PB_EXEC", "1");
    SetEnvironmentVariableA("RECOMP_FB_WINDOW", "1");
    SetEnvironmentVariableA("RECOMP_KEYBOARD", "1");
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
    snprintf(log, sizeof log, "%s\\fbos.log", s_root);
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
        snprintf(msg, sizeof msg, "Could not start bin\\fbos.exe (error %lu).",
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
            if (play(h))
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
    RECT r = { 0, 0, 332, 408 };
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
