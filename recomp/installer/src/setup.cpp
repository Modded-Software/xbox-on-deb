#include <windows.h>
#include <mmsystem.h>
#include <shellapi.h>
#include <shlobj.h>
#include <shlwapi.h>
#include <objbase.h>
#include <gdiplus.h>
#include <stdio.h>
#include <string>
#include <vector>
#include <algorithm>
#include <cstdarg>

#pragma comment(lib, "gdiplus.lib")
#pragma comment(lib, "winmm.lib")

using namespace Gdiplus;

static const wchar_t *kTitle = L"StarCraft: Ghost Recompiled Installer";
static const int kW = 640;
static const int kH = 480;
static const int kMenuX = 28;
static const int kMenuY = 168;
static const int kMenuH = 32;
static const COLORREF kGold = RGB(140, 232, 180);
static const COLORREF kGoldHi = RGB(255, 255, 128);
static const COLORREF kGoldDim = RGB(144, 144, 160);
static const COLORREF kAccel = RGB(255, 255, 255);
static const COLORREF kWarn = RGB(224, 64, 64);

enum Page { PAGE_MENU, PAGE_LOCATE, PAGE_OPTIONS, PAGE_PROGRESS, PAGE_FINISH, PAGE_ABOUT, PAGE_REMOVE, PAGE_LAUNCH };
enum Splash { SPL_MENU, SPL_LOCATE, SPL_OPTIONS, SPL_PROGRESS, SPL_FINISH, SPL_ABOUT, SPL_REPAIR, SPL_LAUNCH, SPL_COUNT };

static const char *kSplashName[SPL_COUNT] = {
    "assets/menu.jpg", "assets/locate.jpg", "assets/options.jpg",
    "assets/progress.jpg", "assets/finish.jpg", "assets/about.jpg", "assets/repair.jpg",
    "assets/launch.jpg"
};

struct Entry {
    uint8_t kind;
    std::string path;
    uint32_t crc;
    const uint8_t *data;
    uint64_t size;
};

struct App {
    HWND hwnd = NULL;
    HWND logwnd = NULL;
    HWND logedit = NULL;
    Page page = PAGE_MENU;
    int menu = -1;
    std::wstring demo;
    std::wstring status;
    bool demo_ok = false;
    bool opt_desktop = true;
    bool opt_start = true;
    bool opt_launch = true;
    bool installed = false;
    int percent = 0;
    std::wstring step;
    bool busy = false;
    bool cancel = false;
    bool failed = false;
    std::wstring log;
    std::vector<Entry> entries;
    const uint8_t *payload = NULL;
    uint64_t payload_size = 0;
    HANDLE map = NULL;
    HANDLE fontmem = NULL;
    Bitmap *splash[SPL_COUNT] = {};
    Bitmap *logo = NULL;
    HFONT font_menu = NULL;
    HFONT font_body = NULL;
    HFONT font_title = NULL;
    HFONT font_small = NULL;
    ULONG_PTR gdip = 0;
    HWND ed_path = NULL;
    HWND btn_browse = NULL;
    HWND btn_back = NULL;
    HWND btn_next = NULL;
    HWND btn_cancel = NULL;
    HWND btn_details = NULL;
    HWND chk_desk = NULL;
    HWND chk_start = NULL;
    HWND chk_launch = NULL;
    HWND cb_res = NULL;
    HWND chk_shadow = NULL;
    HWND cb_input = NULL;
    int res_index = 3;
    bool shadow_high = true;
    bool input_kbm = true;
    bool sound_on = true;
};

static App g;

static void log_line(const wchar_t *fmt, ...);
static bool provision_launcher(std::wstring *desktop_unix);
static bool run_unix(const std::wstring &args);

static uint32_t crc32(const uint8_t *p, size_t n)
{
    uint32_t c = 0xFFFFFFFFu;
    for (size_t i = 0; i < n; i++) {
        c ^= p[i];
        for (int b = 0; b < 8; b++)
            c = (c >> 1) ^ (0xEDB88320u & (uint32_t)-(int)(c & 1));
    }
    return ~c;
}

static std::wstring widen(const std::string &s)
{
    if (s.empty()) return L"";
    int n = MultiByteToWideChar(CP_UTF8, 0, s.data(), (int)s.size(), NULL, 0);
    std::wstring w(n, 0);
    MultiByteToWideChar(CP_UTF8, 0, s.data(), (int)s.size(), &w[0], n);
    return w;
}

static std::string narrow(const std::wstring &w)
{
    if (w.empty()) return "";
    int n = WideCharToMultiByte(CP_UTF8, 0, w.data(), (int)w.size(), NULL, 0, NULL, NULL);
    std::string s(n, 0);
    WideCharToMultiByte(CP_UTF8, 0, w.data(), (int)w.size(), &s[0], n, NULL, NULL);
    return s;
}

static bool file_is(const std::wstring &p, bool dir)
{
    DWORD a = GetFileAttributesW(p.c_str());
    if (a == INVALID_FILE_ATTRIBUTES) return false;
    bool d = (a & FILE_ATTRIBUTE_DIRECTORY) != 0;
    return dir ? d : !d;
}

static bool read_xbe_magic(const std::wstring &p)
{
    HANDLE h = CreateFileW(p.c_str(), GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) return false;
    char m[4] = {};
    DWORD n = 0;
    ReadFile(h, m, 4, &n, NULL);
    CloseHandle(h);
    return n == 4 && memcmp(m, "XBEH", 4) == 0;
}

static bool validate_demo(const std::wstring &dir)
{
    if (dir.empty()) return false;
    if (!read_xbe_magic(dir + L"\\Ghost.xbe")) return false;
    return file_is(dir + L"\\Materials", true) && file_is(dir + L"\\Sounds", true)
        && file_is(dir + L"\\3D", true) && file_is(dir + L"\\Levels", true);
}

static std::wstring exe_dir()
{
    wchar_t buf[MAX_PATH];
    GetModuleFileNameW(NULL, buf, MAX_PATH);
    PathRemoveFileSpecW(buf);
    return buf;
}

static std::wstring self_path()
{
    wchar_t buf[MAX_PATH];
    GetModuleFileNameW(NULL, buf, MAX_PATH);
    return buf;
}

static void set_status()
{
    g.demo_ok = validate_demo(g.demo);
    g.installed = g.demo_ok && file_is(g.demo + L"\\GhostRecomp.exe", false);
    if (g.demo.empty())
        g.status = L"No folder selected.";
    else if (!g.demo_ok)
        g.status = L"Ghost.xbe (XBEH) + Materials/Sounds/3D/Levels not found.";
    else if (g.installed)
        g.status = L"Demo folder found. Already installed (repair).";
    else
        g.status = L"Demo folder found.";
}

static const wchar_t *kResSel[4] = {
    L"640 x 480", L"1024 x 768", L"1280 x 720", L"1920 x 1080"
};
static const wchar_t *kResArg[4] = {
    L"640x480", L"1024x768", L"1280x720", L"1920x1080"
};

static const wchar_t *kSettingsKey = L"Software\\xbox-on-deb\\StarCraftGhostRecomp";

static void load_settings()
{
    HKEY k;
    if (RegOpenKeyExW(HKEY_CURRENT_USER, kSettingsKey, 0, KEY_QUERY_VALUE, &k) != ERROR_SUCCESS)
        return;
    wchar_t buf[64];
    DWORD n = sizeof(buf), typ = 0;
    if (RegQueryValueExW(k, L"Resolution", NULL, &typ, (BYTE *)buf, &n) == ERROR_SUCCESS && typ == REG_SZ) {
        for (int i = 0; i < 4; i++)
            if (!wcscmp(buf, kResArg[i])) g.res_index = i;
    }
    DWORD v = 0, sz = sizeof(v);
    if (RegQueryValueExW(k, L"ShadowHigh", NULL, &typ, (BYTE *)&v, &sz) == ERROR_SUCCESS && typ == REG_DWORD)
        g.shadow_high = v != 0;
    v = 0; sz = sizeof(v);
    if (RegQueryValueExW(k, L"InputKbm", NULL, &typ, (BYTE *)&v, &sz) == ERROR_SUCCESS && typ == REG_DWORD)
        g.input_kbm = v != 0;
    RegCloseKey(k);
}

static bool running_under_wine()
{
    HMODULE ntdll = GetModuleHandleW(L"ntdll.dll");
    return ntdll && GetProcAddress(ntdll, "wine_get_version") != NULL;
}

static bool write_launch_cfg()
{
    if (!running_under_wine()) return false;
    std::string cfg = "RES=" + narrow(kResArg[g.res_index]) + "\n";
    cfg += std::string("SHADOW=") + (g.shadow_high ? "1024" : "512") + "\n";
    cfg += std::string("KBM=") + (g.input_kbm ? "1" : "0") + "\n";
    std::wstring path = g.demo + L"\\GhostRecomp-launch.cfg";
    HANDLE h = CreateFileW(path.c_str(), GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) return false;
    DWORD n = 0;
    BOOL ok = WriteFile(h, cfg.data(), (DWORD)cfg.size(), &n, NULL);
    CloseHandle(h);
    return ok && n == (DWORD)cfg.size();
}

static void save_settings()
{
    HKEY k;
    if (RegCreateKeyExW(HKEY_CURRENT_USER, kSettingsKey, 0, NULL, 0,
            KEY_SET_VALUE, NULL, &k, NULL) != ERROR_SUCCESS)
        return;
    RegSetValueExW(k, L"Resolution", 0, REG_SZ, (const BYTE *)kResArg[g.res_index],
                   (DWORD)((wcslen(kResArg[g.res_index]) + 1) * sizeof(wchar_t)));
    DWORD v = g.shadow_high ? 1 : 0;
    RegSetValueExW(k, L"ShadowHigh", 0, REG_DWORD, (const BYTE *)&v, sizeof(v));
    v = g.input_kbm ? 1 : 0;
    RegSetValueExW(k, L"InputKbm", 0, REG_DWORD, (const BYTE *)&v, sizeof(v));
    RegCloseKey(k);
    write_launch_cfg();
}

static bool load_payload()
{
    std::wstring path = self_path();
    HANDLE h = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) return false;
    LARGE_INTEGER sz;
    GetFileSizeEx(h, &sz);
    if (sz.QuadPart < 64) { CloseHandle(h); return false; }
    g.map = CreateFileMappingW(h, NULL, PAGE_READONLY, 0, 0, NULL);
    CloseHandle(h);
    if (!g.map) return false;
    const uint8_t *base = (const uint8_t *)MapViewOfFile(g.map, FILE_MAP_READ, 0, 0, 0);
    if (!base) return false;
    const uint8_t *foot = base + sz.QuadPart - 32;
    if (memcmp(foot, "SGHRPKG1", 8) != 0) return false;
    uint32_t ver = *(const uint32_t *)(foot + 8);
    uint64_t off = *(const uint64_t *)(foot + 12);
    uint64_t size = *(const uint64_t *)(foot + 20);
    uint32_t expect = *(const uint32_t *)(foot + 28);
    if (ver != 1 || (int64_t)off + (int64_t)size + 32 != sz.QuadPart) return false;
    const uint8_t *body = base + off;
    if (crc32(body, (size_t)size) != expect || memcmp(body, "SGHRPAY1", 8) != 0) return false;
    uint32_t count = *(const uint32_t *)(body + 12);
    const uint8_t *p = body + 16;
    const uint8_t *end = body + size;
    for (uint32_t i = 0; i < count; i++) {
        if (p + 16 > end) return false;
        Entry e;
        e.kind = p[0];
        uint16_t plen = *(const uint16_t *)(p + 2);
        e.crc = *(const uint32_t *)(p + 4);
        e.size = *(const uint64_t *)(p + 8);
        p += 16;
        if (p + plen + e.size > end) return false;
        e.path.assign((const char *)p, plen);
        p += plen;
        e.data = p;
        p += e.size;
        g.entries.push_back(e);
    }
    g.payload = body;
    g.payload_size = size;
    return true;
}

static const Entry *find_entry(const char *name)
{
    for (auto &e : g.entries)
        if (e.path == name) return &e;
    return NULL;
}

static Bitmap *bitmap_from(const uint8_t *data, size_t n)
{
    HGLOBAL hg = GlobalAlloc(GMEM_MOVEABLE, n);
    if (!hg) return NULL;
    void *p = GlobalLock(hg);
    memcpy(p, data, n);
    GlobalUnlock(hg);
    IStream *st = NULL;
    if (FAILED(CreateStreamOnHGlobal(hg, TRUE, &st))) { GlobalFree(hg); return NULL; }
    Bitmap *b = Bitmap::FromStream(st);
    st->Release();
    if (!b || b->GetLastStatus() != Ok) { delete b; return NULL; }
    return b;
}

static void load_font_mem()
{
    const Entry *e = find_entry("assets/eurostile.otf");
    if (!e) return;
    DWORD n = 0;
    g.fontmem = AddFontMemResourceEx((void *)e->data, (DWORD)e->size, NULL, &n);
}

static Bitmap *dim_bitmap(Bitmap *src, float factor)
{
    if (!src) return NULL;
    int w = (int)src->GetWidth();
    int h = (int)src->GetHeight();
    Bitmap *dst = new Bitmap(w, h, PixelFormat32bppARGB);
    if (!dst || dst->GetLastStatus() != Ok) { delete dst; return src; }
    Graphics gr(dst);
    ColorMatrix cm = {};
    cm.m[0][0] = factor;
    cm.m[1][1] = factor;
    cm.m[2][2] = factor;
    cm.m[3][3] = 1.0f;
    cm.m[4][4] = 1.0f;
    ImageAttributes ia;
    ia.SetColorMatrix(&cm);
    gr.DrawImage(src, Rect(0, 0, w, h), 0, 0, w, h, UnitPixel, &ia);
    delete src;
    return dst;
}

static void load_splashes()
{
    for (int i = 0; i < SPL_COUNT; i++) {
        const Entry *e = find_entry(kSplashName[i]);
        if (e) g.splash[i] = dim_bitmap(bitmap_from(e->data, (size_t)e->size), 0.67f);
    }
    const Entry *logo = find_entry("assets/logo.png");
    if (logo) g.logo = bitmap_from(logo->data, (size_t)logo->size);
}

static void start_music()
{
    if (!g.sound_on) return;
    const Entry *e = find_entry("assets/title.wav");
    if (!e) return;
    PlaySoundA((LPCSTR)e->data, NULL, SND_MEMORY | SND_ASYNC | SND_LOOP | SND_NODEFAULT);
}

static void stop_music()
{
    PlaySoundA(NULL, NULL, 0);
}

static bool sound_hit(int x, int y)
{
    return x >= 566 && x < 612 && y >= 8 && y < 50;
}

static void toggle_sound()
{
    g.sound_on = !g.sound_on;
    if (g.sound_on) start_music();
    else stop_music();
}

static void draw_sound_icon(HDC dc)
{
    int x = 580, y = 20;
    COLORREF c = g.sound_on ? kGold : kGoldDim;
    HBRUSH br = CreateSolidBrush(c);
    HPEN pen = CreatePen(PS_SOLID, 1, c);
    HGDIOBJ ob = SelectObject(dc, br);
    HGDIOBJ op = SelectObject(dc, pen);
    RECT body = {x, y + 7, x + 5, y + 13};
    FillRect(dc, &body, br);
    POINT cone[3] = { {x + 5, y + 10}, {x + 12, y + 2}, {x + 12, y + 18} };
    Polygon(dc, cone, 3);
    if (g.sound_on) {
        POINT w1[4] = { {x + 18, y + 6}, {x + 20, y + 8},
                        {x + 20, y + 12}, {x + 18, y + 14} };
        POINT w2[4] = { {x + 23, y + 4}, {x + 25, y + 7},
                        {x + 25, y + 13}, {x + 23, y + 16} };
        Polyline(dc, w1, 4);
        Polyline(dc, w2, 4);
    } else {
        HPEN slash = CreatePen(PS_SOLID, 1, c);
        HGDIOBJ os = SelectObject(dc, slash);
        MoveToEx(dc, x + 18, y + 5, NULL);
        LineTo(dc, x + 25, y + 15);
        MoveToEx(dc, x + 25, y + 5, NULL);
        LineTo(dc, x + 18, y + 15);
        SelectObject(dc, os);
        DeleteObject(slash);
    }
    SelectObject(dc, ob);
    SelectObject(dc, op);
    DeleteObject(br);
    DeleteObject(pen);
}

static int splash_for(Page p)
{
    switch (p) {
    case PAGE_MENU: return SPL_MENU;
    case PAGE_LOCATE: return SPL_LOCATE;
    case PAGE_OPTIONS: return SPL_OPTIONS;
    case PAGE_PROGRESS: return SPL_PROGRESS;
    case PAGE_FINISH: return SPL_FINISH;
    case PAGE_ABOUT: return SPL_ABOUT;
    case PAGE_LAUNCH: return SPL_LAUNCH;
    default: return SPL_REPAIR;
    }
}

static void draw_text(HDC dc, HFONT f, COLORREF c, int x, int y, const wchar_t *s)
{
    HFONT old = (HFONT)SelectObject(dc, f);
    SetBkMode(dc, TRANSPARENT);
    SetTextCharacterExtra(dc, 0);
    SetTextColor(dc, RGB(20, 12, 0));
    TextOutW(dc, x + 1, y + 1, s, (int)wcslen(s));
    SetTextColor(dc, c);
    TextOutW(dc, x, y, s, (int)wcslen(s));
    SetTextCharacterExtra(dc, 0);
    SelectObject(dc, old);
}

static void draw_bar(HDC dc, int x, int y, int w, int h, int pct)
{
    RECT r = {x, y, x + w, y + h};
    DrawEdge(dc, &r, EDGE_SUNKEN, BF_RECT);
    int inner = w - 6;
    int fill = inner * pct / 100;
    HBRUSH br = CreateSolidBrush(RGB(220, 180, 40));
    RECT f = {x + 3, y + 3, x + 3 + fill, y + h - 3};
    FillRect(dc, &f, br);
    DeleteObject(br);
}

struct MenuItem { const wchar_t *text; int accel; };
static const MenuItem kMenu[] = {
    { L"Install StarCraft: Ghost Recompiled", 0 },
    { L"Change Install Folder...", 15 },
    { L"Remove Installation", 2 },
    { L"About", 0 },
    { L"Exit Installer", 1 },
    { L"Launch Game", 3 },
};
static const int kMenuN = 6;
static const int kMenuRow[kMenuN] = { 173, 225, 257, 325, 425, 425 };

static int menu_visible(int *ids)
{
    int k = 0;
    ids[k++] = 0;
    if (g.installed) { ids[k++] = 1; ids[k++] = 2; }
    ids[k++] = 3;
    ids[k++] = 4;
    if (g.installed) ids[k++] = 5;
    return k;
}

static bool menu_id_visible(int id)
{
    if (id == 0 || id == 3 || id == 4) return true;
    return g.installed;
}

static void menu_step(int dir)
{
    int ids[kMenuN];
    int n = menu_visible(ids);
    int pos = -1;
    for (int k = 0; k < n; k++)
        if (ids[k] == g.menu) pos = k;
    if (pos < 0) pos = (dir > 0) ? n - 1 : 0;
    pos = (pos + dir + n) % n;
    g.menu = ids[pos];
}


static void draw_accel(HDC dc, HFONT f, COLORREF c, int x, int y, const wchar_t *s, int accel, bool on)
{
    HFONT old = (HFONT)SelectObject(dc, f);
    SetBkMode(dc, TRANSPARENT);
    SetTextCharacterExtra(dc, 0);
    int n = (int)wcslen(s);
    SetTextColor(dc, RGB(12, 8, 0));
    TextOutW(dc, x + 1, y + 1, s, n);
    SetTextColor(dc, on ? kAccel : c);
    TextOutW(dc, x, y, s, n);
    if (accel >= 0 && accel < n) {
        SIZE pre = {};
        GetTextExtentPoint32W(dc, s, accel, &pre);
        SetTextColor(dc, kAccel);
        TextOutW(dc, x + pre.cx, y, s + accel, 1);
    }
    SetTextCharacterExtra(dc, 0);
    SelectObject(dc, old);
}

static void paint(HWND hwnd)
{
    PAINTSTRUCT ps;
    HDC dc = BeginPaint(hwnd, &ps);
    RECT rc; GetClientRect(hwnd, &rc);
    HDC mem = CreateCompatibleDC(dc);
    HBITMAP bm = CreateCompatibleBitmap(dc, rc.right, rc.bottom);
    HBITMAP old = (HBITMAP)SelectObject(mem, bm);

    Graphics gr(mem);
    gr.SetInterpolationMode(InterpolationModeHighQualityBicubic);
    HBRUSH black = CreateSolidBrush(RGB(0, 0, 0));
    FillRect(mem, &rc, black);
    DeleteObject(black);
    Bitmap *bg = g.splash[splash_for(g.page)];
    if (bg) {
        int sw = (int)bg->GetWidth(), sh = (int)bg->GetHeight();
        if (sw > 0 && sh > 0) {
            float s = std::min((float)rc.right / sw, (float)rc.bottom / sh);
            int dw = (int)(sw * s + 0.5f), dh = (int)(sh * s + 0.5f);
            gr.DrawImage(bg, (rc.right - dw) / 2, (rc.bottom - dh) / 2, dw, dh);
        }
    }
    if (g.logo) {
        int lw = 420;
        int lh = lw * (int)g.logo->GetHeight() / (int)g.logo->GetWidth();
        gr.DrawImage(g.logo, 16, 8, lw, lh);
    }

    if (g.page == PAGE_MENU) {
        int ids[kMenuN];
        int n = menu_visible(ids);
        for (int p = 0; p < n; p++) {
            int i = ids[p];
            bool on = i == g.menu;
            HFONT fnt = g.font_menu;
            const wchar_t *txt = kMenu[i].text;
            if (i == 0) {
                fnt = g.font_title;
                txt = g.installed ? L"Reinstall StarCraft: Ghost Recompiled" : L"Install StarCraft: Ghost Recompiled";
            }
            int x = kMenuX;
            if (i == 5) {
                HFONT old = (HFONT)SelectObject(mem, fnt);
                SIZE sz = {};
                GetTextExtentPoint32W(mem, txt, (int)wcslen(txt), &sz);
                SelectObject(mem, old);
                x = 612 - sz.cx;
            }
            draw_accel(mem, fnt, kGold, x, kMenuRow[i], txt, kMenu[i].accel, on);
        }
    } else if (g.page == PAGE_LOCATE) {
        draw_text(mem, g.font_menu, kGold, kMenuX, 150, L"Select the Xbox demo folder");
        draw_text(mem, g.font_body, g.demo_ok ? RGB(176, 220, 96) : RGB(255, 96, 64),
                  kMenuX, 230, g.status.c_str());
    } else if (g.page == PAGE_OPTIONS) {
        draw_text(mem, g.font_menu, kGold, kMenuX, 150, L"Install options");
        draw_text(mem, g.font_body, kGold, kMenuX, 300,
                  L"Does not modify the original game files.");
        draw_text(mem, g.font_small, kGoldDim, kMenuX, 324, g.demo.c_str());
    } else if (g.page == PAGE_PROGRESS) {
        draw_text(mem, g.font_menu, kGold, kMenuX, 150, L"Installing recompiled runtime");
        draw_text(mem, g.font_body, kGoldHi, kMenuX, 190, g.step.c_str());
        draw_bar(mem, kMenuX, 220, 560, 22, g.percent);
        wchar_t pct[16];
        swprintf(pct, 16, L"%d%%", g.percent);
        draw_text(mem, g.font_body, kGold, kMenuX, 250, pct);
    } else if (g.page == PAGE_FINISH) {
        draw_text(mem, g.font_menu, kGold, kMenuX, 160,
                  g.failed ? L"Installation failed" : L"Installation complete");
        draw_text(mem, g.font_body, kGoldHi, kMenuX, 210,
                  g.failed ? L"See the details log." : L"StarCraft: Ghost Recompiled is ready.");
        draw_text(mem, g.font_small, kGoldDim, kMenuX, 240, g.demo.c_str());
    } else if (g.page == PAGE_ABOUT) {
        draw_text(mem, g.font_menu, kGold, kMenuX, 150, L"About");
        const wchar_t *lines[] = {
            L"StarCraft: Ghost Recompiled Installer 1.0",
            L"Installs the recompiled Xbox demo runtime",
            L"into your existing demo folder.",
            L"No game data is included.",
            L"Splash art and logo: Blizzard Entertainment.",
            L"Personal use only. Do not redistribute."
        };
        for (int i = 0; i < 6; i++)
            draw_text(mem, g.font_body, kGoldHi, kMenuX, 190 + i * 22, lines[i]);
        draw_text(mem, g.font_body, kGoldHi, kMenuX, 344,
                  L"THIS IS AN UNOFFICIAL PROJECT");
        draw_text(mem, g.font_small, kWarn, kMenuX, 366,
                  L"Not affiliated with or supported by Blizzard Entertainment.");
    } else if (g.page == PAGE_LAUNCH) {
        draw_text(mem, g.font_menu, kGold, kMenuX, 150, L"Launch StarCraft: Ghost");
        draw_text(mem, g.font_small, kGoldDim, kMenuX, 198, L"Resolution");
        draw_text(mem, g.font_small, kGoldDim, kMenuX, 262, L"Graphics");
        draw_text(mem, g.font_small, kGoldDim, kMenuX, 300, L"Input");
        const wchar_t *play = L"Play StarCraft: Ghost Recompiled";
        HFONT old = (HFONT)SelectObject(mem, g.font_menu);
        SIZE sz = {};
        GetTextExtentPoint32W(mem, play, (int)wcslen(play), &sz);
        SelectObject(mem, old);
        draw_accel(mem, g.font_menu, kGold, 612 - sz.cx, 430, play, 3, g.menu == 100);
    } else if (g.page == PAGE_REMOVE) {
        draw_text(mem, g.font_menu, kGold, kMenuX, 160, L"Remove installation?");
        draw_text(mem, g.font_body, kGoldHi, kMenuX, 210,
                  L"Removes GhostRecomp.exe and shortcuts only.");
        draw_text(mem, g.font_small, kGoldDim, kMenuX, 240, g.demo.c_str());
    }

    draw_sound_icon(mem);

    BitBlt(dc, 0, 0, rc.right, rc.bottom, mem, 0, 0, SRCCOPY);
    SelectObject(mem, old);
    DeleteObject(bm);
    DeleteDC(mem);
    EndPaint(hwnd, &ps);
}

static void show(HWND h, bool on)
{
    if (h) ShowWindow(h, on ? SW_SHOW : SW_HIDE);
}

static void layout_controls()
{
    bool loc = g.page == PAGE_LOCATE;
    bool opt = g.page == PAGE_OPTIONS;
    bool prog = g.page == PAGE_PROGRESS;
    bool fin = g.page == PAGE_FINISH;
    bool rem = g.page == PAGE_REMOVE;
    bool lau = g.page == PAGE_LAUNCH;
    bool nav = loc || opt || fin || g.page == PAGE_ABOUT || rem || lau;
    show(g.ed_path, loc);
    show(g.btn_browse, loc);
    show(g.chk_desk, opt);
    show(g.chk_start, opt);
    show(g.chk_launch, opt);
    show(g.cb_res, lau);
    show(g.chk_shadow, lau);
    show(g.cb_input, lau);
    show(g.btn_details, prog || fin);
    show(g.btn_back, nav && !prog);
    show(g.btn_next, nav && !lau && g.page != PAGE_ABOUT);
    show(g.btn_cancel, loc || opt || prog || rem);
    if (loc) SetWindowTextW(g.btn_next, L"Next >");
    else if (opt) SetWindowTextW(g.btn_next, L"Install");
    else if (fin) SetWindowTextW(g.btn_next, L"Finish");
    else if (rem) SetWindowTextW(g.btn_next, L"Remove");
    else if (g.page == PAGE_ABOUT) SetWindowTextW(g.btn_next, L"Back");
    SetWindowTextW(g.ed_path, g.demo.c_str());
    SendMessageW(g.chk_desk, BM_SETCHECK, g.opt_desktop ? BST_CHECKED : BST_UNCHECKED, 0);
    SendMessageW(g.chk_start, BM_SETCHECK, g.opt_start ? BST_CHECKED : BST_UNCHECKED, 0);
    SendMessageW(g.chk_launch, BM_SETCHECK, g.opt_launch ? BST_CHECKED : BST_UNCHECKED, 0);
    SendMessageW(g.cb_res, CB_SETCURSEL, g.res_index, 0);
    SendMessageW(g.chk_shadow, BM_SETCHECK, g.shadow_high ? BST_CHECKED : BST_UNCHECKED, 0);
    SendMessageW(g.cb_input, CB_SETCURSEL, g.input_kbm ? 1 : 0, 0);
}

static void goto_page(Page p)
{
    g.page = p;
    g.menu = -1;
    layout_controls();
    InvalidateRect(g.hwnd, NULL, FALSE);
}

static void read_options()
{
    wchar_t buf[MAX_PATH * 2];
    GetWindowTextW(g.ed_path, buf, MAX_PATH * 2);
    if (g.page == PAGE_LOCATE) g.demo = buf;
    g.opt_desktop = SendMessageW(g.chk_desk, BM_GETCHECK, 0, 0) == BST_CHECKED;
    g.opt_start = SendMessageW(g.chk_start, BM_GETCHECK, 0, 0) == BST_CHECKED;
    g.opt_launch = SendMessageW(g.chk_launch, BM_GETCHECK, 0, 0) == BST_CHECKED;
    set_status();
}

static void append_log(const std::wstring &line)
{
    SYSTEMTIME st; GetLocalTime(&st);
    wchar_t ts[32];
    swprintf(ts, 32, L"[%02d:%02d:%02d] ", st.wHour, st.wMinute, st.wSecond);
    g.log += ts;
    g.log += line;
    g.log += L"\r\n";
    if (g.logedit) {
        int len = GetWindowTextLengthW(g.logedit);
        SendMessageW(g.logedit, EM_SETSEL, len, len);
        std::wstring chunk = ts + line + L"\r\n";
        SendMessageW(g.logedit, EM_REPLACESEL, FALSE, (LPARAM)chunk.c_str());
    }
}

static void log_line(const wchar_t *fmt, ...)
{
    wchar_t buf[1024];
    va_list ap; va_start(ap, fmt);
    vswprintf(buf, 1024, fmt, ap);
    va_end(ap);
    append_log(buf);
}

static void save_log_file()
{
    if (g.demo.empty()) return;
    std::wstring p = g.demo + L"\\GhostRecomp-install.log";
    HANDLE h = CreateFileW(p.c_str(), GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) return;
    std::string s = narrow(g.log);
    DWORD n = 0;
    WriteFile(h, s.data(), (DWORD)s.size(), &n, NULL);
    CloseHandle(h);
}

static LRESULT CALLBACK log_proc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
    if (msg == WM_CLOSE) { ShowWindow(hwnd, SW_HIDE); return 0; }
    if (msg == WM_SIZE && g.logedit) {
        RECT r; GetClientRect(hwnd, &r);
        MoveWindow(g.logedit, 8, 8, r.right - 16, r.bottom - 16, TRUE);
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

static void toggle_log()
{
    if (!g.logwnd) {
        WNDCLASSW wc = {};
        wc.lpfnWndProc = log_proc;
        wc.hInstance = GetModuleHandleW(NULL);
        wc.lpszClassName = L"SGSetupLog";
        wc.hbrBackground = (HBRUSH)(COLOR_BTNFACE + 1);
        wc.hCursor = LoadCursor(NULL, IDC_ARROW);
        RegisterClassW(&wc);
        g.logwnd = CreateWindowExW(WS_EX_TOOLWINDOW, L"SGSetupLog", L"Details",
            WS_OVERLAPPEDWINDOW | WS_VISIBLE, 80, 80, 520, 320,
            g.hwnd, NULL, wc.hInstance, NULL);
        g.logedit = CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", g.log.c_str(),
            WS_CHILD | WS_VISIBLE | WS_VSCROLL | ES_MULTILINE | ES_AUTOVSCROLL | ES_READONLY,
            8, 8, 490, 260, g.logwnd, NULL, wc.hInstance, NULL);
        SendMessageW(g.logedit, WM_SETFONT, (WPARAM)g.font_body, TRUE);
    } else {
        ShowWindow(g.logwnd, IsWindowVisible(g.logwnd) ? SW_HIDE : SW_SHOW);
    }
}

static bool write_file(const std::wstring &path, const uint8_t *data, uint64_t size, uint32_t expect)
{
    std::wstring tmp = path + L".tmp";
    HANDLE h = CreateFileW(tmp.c_str(), GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) return false;
    uint64_t left = size;
    const uint8_t *p = data;
    uint32_t c = 0xFFFFFFFFu;
    while (left) {
        DWORD chunk = (DWORD)std::min<uint64_t>(left, 1 << 20);
        DWORD n = 0;
        if (!WriteFile(h, p, chunk, &n, NULL) || n != chunk) { CloseHandle(h); DeleteFileW(tmp.c_str()); return false; }
        for (DWORD i = 0; i < n; i++) {
            c ^= p[i];
            for (int b = 0; b < 8; b++) c = (c >> 1) ^ (0xEDB88320u & (uint32_t)-(int)(c & 1));
        }
        p += n;
        left -= n;
        if (size) g.percent = 15 + (int)(((size - left) * 55) / size);
        PostMessageW(g.hwnd, WM_APP + 1, 0, 0);
        if (g.cancel) { CloseHandle(h); DeleteFileW(tmp.c_str()); return false; }
    }
    CloseHandle(h);
    if (~c != expect) { DeleteFileW(tmp.c_str()); return false; }
    if (!MoveFileExW(tmp.c_str(), path.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileW(tmp.c_str());
        return false;
    }
    return true;
}

static bool make_shortcut(const std::wstring &lnk, const std::wstring &target, const std::wstring &workdir)
{
    IShellLinkW *sl = NULL;
    if (FAILED(CoCreateInstance(CLSID_ShellLink, NULL, CLSCTX_INPROC_SERVER, IID_IShellLinkW, (void **)&sl)))
        return false;
    sl->SetPath(target.c_str());
    sl->SetWorkingDirectory(workdir.c_str());
    sl->SetDescription(L"StarCraft: Ghost Recompiled");
    IPersistFile *pf = NULL;
    bool ok = SUCCEEDED(sl->QueryInterface(IID_IPersistFile, (void **)&pf))
        && SUCCEEDED(pf->Save(lnk.c_str(), TRUE));
    if (pf) pf->Release();
    sl->Release();
    return ok;
}

static bool write_reg()
{
    HKEY k;
    if (RegCreateKeyExW(HKEY_CURRENT_USER,
            L"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\StarCraftGhostRecomp",
            0, NULL, 0, KEY_SET_VALUE, NULL, &k, NULL) != ERROR_SUCCESS)
        return false;
    auto set = [&](const wchar_t *n, const std::wstring &v) {
        RegSetValueExW(k, n, 0, REG_SZ, (const BYTE *)v.c_str(), (DWORD)((v.size() + 1) * sizeof(wchar_t)));
    };
    set(L"DisplayName", L"StarCraft: Ghost Recompiled");
    set(L"DisplayVersion", L"1.0.0");
    set(L"Publisher", L"xbox-on-deb");
    set(L"InstallLocation", g.demo);
    set(L"UninstallString", L"\"" + g.demo + L"\\GhostRecomp-Uninstall.exe\"");
    DWORD no = 1;
    RegSetValueExW(k, L"NoModify", 0, REG_DWORD, (const BYTE *)&no, sizeof(no));
    RegCloseKey(k);
    if (RegCreateKeyExW(HKEY_CURRENT_USER, L"Software\\xbox-on-deb\\StarCraftGhostRecomp",
            0, NULL, 0, KEY_SET_VALUE, NULL, &k, NULL) == ERROR_SUCCESS) {
        set(L"InstallPath", g.demo);
        RegCloseKey(k);
    }
    return true;
}

static bool write_manifest(const std::vector<std::wstring> &lines)
{
    std::wstring p = g.demo + L"\\GhostRecomp.manifest";
    HANDLE h = CreateFileW(p.c_str(), GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) return false;
    for (auto &ln : lines) {
        std::string s = narrow(ln) + "\r\n";
        DWORD n = 0;
        WriteFile(h, s.data(), (DWORD)s.size(), &n, NULL);
    }
    CloseHandle(h);
    return true;
}

static std::wstring known_folder(int csidl)
{
    wchar_t buf[MAX_PATH];
    if (FAILED(SHGetFolderPathW(NULL, csidl, NULL, 0, buf))) return L"";
    return buf;
}

static DWORD WINAPI install_thread(LPVOID)
{
    CoInitializeEx(NULL, COINIT_APARTMENTTHREADED);
    g.failed = false;
    g.cancel = false;
    g.step = L"Verifying package...";
    g.percent = 5;
    PostMessageW(g.hwnd, WM_APP + 1, 0, 0);
    log_line(L"Target: %s", g.demo.c_str());

    const Entry *exe = find_entry("GhostRecomp.exe");
    const Entry *un = find_entry("GhostRecomp-Uninstall.exe");
    if (!exe || !un) {
        log_line(L"Package is missing the runtime.");
        g.failed = true;
        PostMessageW(g.hwnd, WM_APP + 2, 0, 0);
        CoUninitialize();
        return 1;
    }
    ULARGE_INTEGER freeb;
    if (GetDiskFreeSpaceExW(g.demo.c_str(), &freeb, NULL, NULL)) {
        uint64_t need = exe->size + un->size + (16ull << 20);
        if (freeb.QuadPart < need) {
            log_line(L"Not enough disk space.");
            g.failed = true;
            PostMessageW(g.hwnd, WM_APP + 2, 0, 0);
            CoUninitialize();
            return 1;
        }
    }
    g.step = L"Unpacking recompiled executable...";
    log_line(L"Writing GhostRecomp.exe (%llu bytes)", (unsigned long long)exe->size);
    if (!write_file(g.demo + L"\\GhostRecomp.exe", exe->data, exe->size, exe->crc)) {
        log_line(g.cancel ? L"Cancelled." : L"Failed to write GhostRecomp.exe");
        g.failed = true;
        PostMessageW(g.hwnd, WM_APP + 2, 0, 0);
        CoUninitialize();
        return 1;
    }
    g.step = L"Writing uninstaller...";
    g.percent = 80;
    log_line(L"Writing GhostRecomp-Uninstall.exe");
    if (!write_file(g.demo + L"\\GhostRecomp-Uninstall.exe", un->data, un->size, un->crc)) {
        log_line(L"Failed to write uninstaller");
        g.failed = true;
        PostMessageW(g.hwnd, WM_APP + 2, 0, 0);
        CoUninitialize();
        return 1;
    }
    g.step = L"Creating shortcuts...";
    g.percent = 88;
    std::wstring launcher_desktop;
    if (provision_launcher(&launcher_desktop))
        log_line(L"Linux launcher + desktop entry");
    std::vector<std::wstring> man;
    man.push_back(L"file=GhostRecomp.exe");
    man.push_back(L"file=GhostRecomp-Uninstall.exe");
    man.push_back(L"file=GhostRecomp.manifest");
    man.push_back(L"file=GhostRecomp-install.log");
    man.push_back(L"file=GhostRecomp-launch.sh");
    man.push_back(L"file=GhostRecomp-launch.cfg");
    man.push_back(L"file=GhostRecomp-launch.desktop");
    man.push_back(L"file=GhostRecomp-provision.sh");
    man.push_back(L"file=GhostRecomp-launch.path");
    if (!launcher_desktop.empty()) man.push_back(L"unixfile=" + launcher_desktop);
    std::wstring target = g.demo + L"\\GhostRecomp.exe";
    if (g.opt_desktop) {
        std::wstring lnk = known_folder(CSIDL_DESKTOPDIRECTORY) + L"\\StarCraft Ghost Recompiled.lnk";
        if (make_shortcut(lnk, target, g.demo)) { log_line(L"Desktop shortcut"); man.push_back(L"shortcut=" + lnk); }
        else log_line(L"WARN desktop shortcut failed");
    }
    if (g.opt_start) {
        std::wstring dir = known_folder(CSIDL_PROGRAMS) + L"\\StarCraft Ghost Recompiled";
        SHCreateDirectoryExW(NULL, dir.c_str(), NULL);
        std::wstring play = dir + L"\\Play StarCraft Ghost.lnk";
        std::wstring rem = dir + L"\\Uninstall StarCraft Ghost Recompiled.lnk";
        if (make_shortcut(play, target, g.demo)) man.push_back(L"shortcut=" + play);
        if (make_shortcut(rem, g.demo + L"\\GhostRecomp-Uninstall.exe", g.demo)) man.push_back(L"shortcut=" + rem);
        log_line(L"Start Menu shortcuts");
        man.push_back(L"dir=" + dir);
    }
    g.step = L"Writing uninstall information...";
    g.percent = 94;
    if (write_reg()) {
        log_line(L"Registry uninstall entry");
        man.push_back(L"reg=HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\StarCraftGhostRecomp");
        man.push_back(L"reg=HKCU\\Software\\xbox-on-deb\\StarCraftGhostRecomp");
    } else log_line(L"WARN registry write failed");
    write_manifest(man);
    save_log_file();
    g.percent = 100;
    g.step = L"Done.";
    g.installed = true;
    log_line(L"Installation complete.");
    PostMessageW(g.hwnd, WM_APP + 2, 0, 0);
    CoUninitialize();
    return 0;
}

static void start_install()
{
    if (!g.demo_ok) {
        MessageBoxW(g.hwnd, L"Select a valid StarCraft: Ghost demo folder first.", kTitle, MB_ICONERROR);
        return;
    }
    g.busy = true;
    g.log.clear();
    goto_page(PAGE_PROGRESS);
    EnableWindow(g.btn_next, FALSE);
    HANDLE th = CreateThread(NULL, 0, install_thread, NULL, 0, NULL);
    if (th) CloseHandle(th);
}

static void browse()
{
    BROWSEINFOW bi = {};
    bi.hwndOwner = g.hwnd;
    bi.lpszTitle = L"Select the StarCraft: Ghost Xbox demo folder";
    bi.ulFlags = BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE;
    PIDLIST_ABSOLUTE pidl = SHBrowseForFolderW(&bi);
    if (!pidl) return;
    wchar_t path[MAX_PATH];
    if (SHGetPathFromIDListW(pidl, path)) {
        g.demo = path;
        set_status();
        SetWindowTextW(g.ed_path, g.demo.c_str());
        InvalidateRect(g.hwnd, NULL, FALSE);
    }
    CoTaskMemFree(pidl);
}

static void detect()
{
    std::vector<std::wstring> cands;
    cands.push_back(exe_dir());
    wchar_t cwd[MAX_PATH];
    if (GetCurrentDirectoryW(MAX_PATH, cwd)) cands.push_back(cwd);
    HKEY k;
    if (RegOpenKeyExW(HKEY_CURRENT_USER, L"Software\\xbox-on-deb\\StarCraftGhostRecomp",
            0, KEY_QUERY_VALUE, &k) == ERROR_SUCCESS) {
        wchar_t buf[MAX_PATH]; DWORD n = sizeof(buf), typ = 0;
        if (RegQueryValueExW(k, L"InstallPath", NULL, &typ, (BYTE *)buf, &n) == ERROR_SUCCESS && typ == REG_SZ)
            cands.push_back(buf);
        RegCloseKey(k);
    }
    DWORD drives = GetLogicalDrives();
    for (int i = 0; i < 26; i++) {
        if (!(drives & (1u << i))) continue;
        wchar_t root[4] = { (wchar_t)(L'A' + i), L':', L'\\', 0 };
        if (GetDriveTypeW(root) != DRIVE_FIXED) continue;
        cands.push_back(std::wstring(root) + L"StarCraft Ghost Xbox Finn Hillbilly");
    }
    for (auto &c : cands) {
        if (validate_demo(c)) { g.demo = c; set_status(); return; }
    }
    g.demo = exe_dir();
    set_status();
}

static bool remove_install()
{
    std::wstring un = g.demo + L"\\GhostRecomp-Uninstall.exe";
    if (!file_is(un, false)) {
        MessageBoxW(g.hwnd, L"Uninstaller not found.", kTitle, MB_ICONERROR);
        return false;
    }
    SHELLEXECUTEINFOW si = {};
    si.cbSize = sizeof(si);
    si.fMask = SEE_MASK_NOCLOSEPROCESS;
    si.lpFile = un.c_str();
    si.lpParameters = L"/quiet";
    si.nShow = SW_HIDE;
    if (!ShellExecuteExW(&si)) return false;
    if (si.hProcess) { WaitForSingleObject(si.hProcess, 60000); CloseHandle(si.hProcess); }
    set_status();
    return true;
}

static std::wstring unix_from_win(const std::wstring &p)
{
    if (p.size() > 2 && p[1] == L':' && (p[0] == L'Z' || p[0] == L'z')) {
        std::wstring s = p.substr(2);
        for (size_t i = 0; i < s.size(); i++)
            if (s[i] == L'\\') s[i] = L'/';
        return s;
    }
    return L"";
}

static std::wstring unix_home()
{
    wchar_t buf[1024];
    DWORD n = GetEnvironmentVariableW(L"HOME", buf, 1024);
    return n ? std::wstring(buf) : L"";
}

static bool write_text_file(const std::wstring &path, const std::string &text)
{
    HANDLE h = CreateFileW(path.c_str(), GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) return false;
    DWORD n = 0;
    BOOL ok = WriteFile(h, text.data(), (DWORD)text.size(), &n, NULL);
    CloseHandle(h);
    return ok && n == (DWORD)text.size();
}

static std::string shell_launcher(const std::string &dir)
{
    const char *lines[] = {
        "#!/bin/bash",
        "set -u",
        "CFG=\"$DIR/GhostRecomp-launch.cfg\"",
        "RES=1920x1080",
        "SHADOW=512",
        "KBM=1",
        "if [ -f \"$CFG\" ]; then . \"$CFG\"; fi",
        "ROOT=\"\"",
        "d=\"$DIR\"",
        "for _ in 1 2 3 4 5 6; do",
        "  if [ -f \"$d/scripts/config.sh\" ]; then ROOT=\"$d\"; break; fi",
        "  d=\"$(dirname \"$d\")\"",
        "done",
        "unset WINEPREFIX WINEDLLOVERRIDES WINEDEBUG",
        "if [ -n \"$ROOT\" ]; then",
        "  cd \"$ROOT\"",
        "  source \"$ROOT/scripts/config.sh\" || exit 1",
        "  detect_ge_proton",
        "else",
        "  export SCGHOST_PREFIX=\"${SCGHOST_PREFIX:-$HOME/Games/scghost-prefix}\"",
        "  export STEAM_ROOT=\"${STEAM_ROOT:-$HOME/.steam/root}\"",
        "  export DRI_PRIME=\"${DRI_PRIME:-pci-0000_09_00_0}\"",
        "  export DXVK_FILTER_DEVICE_UUID=\"${DXVK_FILTER_DEVICE_UUID:-8680a0560800000009000000000000}\"",
        "  export DXVK_CONFIG=\"${DXVK_CONFIG:-d3d11.cachedDynamicResources = vic}\"",
        "  GE_PROTON_DIR=\"\"",
        "  for p in \"$STEAM_ROOT\"/compatibilitytools.d/GE-Proton*/; do",
        "    if [ -f \"$p/proton\" ] && [ -f \"$p/files/bin/wine\" ]; then GE_PROTON_DIR=\"$p\"; break; fi",
        "  done",
        "fi",
        "if [ -z \"${GE_PROTON_DIR:-}\" ]; then echo \"GE-Proton not found\"; exit 1; fi",
        "export STEAM_COMPAT_CLIENT_INSTALL_PATH=\"$STEAM_ROOT\"",
        "export STEAM_COMPAT_DATA_PATH=\"$SCGHOST_PREFIX\"",
        "export PROTON_USE_NTSYNC=1 PROTON_NO_XIM=1 WINE_ALLOW_XIM=0 XMODIFIERS=@im=none",
        "export SCGHOST_SHADOW_TEX=\"$SHADOW\"",
        "export RECOMP_AC97_READY=1",
        "export RECOMP_LOG=\"$DIR/GhostRecomp-runtime.log\"",
        "ARGS=(\"--resolution=$RES\")",
        "if [ \"$KBM\" = 1 ]; then ARGS+=(--kbm); fi",
        "cd \"$DIR\"",
        "exec \"$GE_PROTON_DIR/proton\" run ./GhostRecomp.exe \"${ARGS[@]}\"",
    };
    std::string s = "DIR=\"" + dir + "\"\n";
    for (size_t i = 0; i < sizeof(lines) / sizeof(lines[0]); i++) {
        s += lines[i];
        s += "\n";
    }
    return s;
}

static std::string read_text_file(const std::wstring &path)
{
    HANDLE h = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) return "";
    DWORD sz = GetFileSize(h, NULL);
    std::string data(sz, 0);
    DWORD n = 0;
    ReadFile(h, &data[0], sz, &n, NULL);
    CloseHandle(h);
    data.resize(n);
    return data;
}

static std::string provision_helper(const std::string &dir)
{
    const char *lines[] = {
        "#!/bin/bash",
        "set -u",
        "APPS=\"$HOME/.local/share/applications\"",
        "mkdir -p \"$APPS\"",
        "cp \"$DIR/GhostRecomp-launch.desktop\" \"$APPS/scghost-recompiled.desktop\"",
        "echo \"$APPS/scghost-recompiled.desktop\" > \"$DIR/GhostRecomp-launch.path\"",
        "if command -v gsettings; then",
        "  cur=$(gsettings get org.gnome.shell favorite-apps)",
        "  case \"$cur\" in",
        "    *scghost-recompiled.desktop*) ;;",
        "    *)",
        "      case \"$cur\" in",
        "        '[]'|'@as []'|'') new=\"['scghost-recompiled.desktop']\" ;;",
        "        *) new=\"${cur%]}, 'scghost-recompiled.desktop']\" ;;",
        "      esac",
        "      gsettings set org.gnome.shell favorite-apps \"$new\"",
        "      ;;",
        "  esac",
        "fi",
    };
    std::string s = "DIR=\"" + dir + "\"\n";
    for (size_t i = 0; i < sizeof(lines) / sizeof(lines[0]); i++) {
        s += lines[i];
        s += "\n";
    }
    return s;
}

static bool provision_launcher(std::wstring *desktop_unix)
{
    if (!running_under_wine()) return false;
    std::wstring script = g.demo + L"\\GhostRecomp-launch.sh";
    std::wstring script_unix = unix_from_win(script);
    if (script_unix.empty()) return false;
    if (!write_text_file(script, shell_launcher(narrow(unix_from_win(g.demo))))) return false;
    write_launch_cfg();

    std::string desk =
        "[Desktop Entry]\n"
        "Name=StarCraft: Ghost Recompiled\n"
        "Comment=Launch the recompiled StarCraft: Ghost\n"
        "Exec=bash \"" + narrow(script_unix) + "\"\n"
        "Icon=scghost\n"
        "Terminal=false\n"
        "Type=Application\n"
        "Categories=Game;\n"
        "StartupNotify=true\n"
        "StartupWMClass=ghost.exe\n";
    if (!write_text_file(g.demo + L"\\GhostRecomp-launch.desktop", desk)) return false;

    std::wstring helper = g.demo + L"\\GhostRecomp-provision.sh";
    if (!write_text_file(helper, provision_helper(narrow(unix_from_win(g.demo))))) return false;
    std::wstring helper_unix = unix_from_win(helper);
    if (helper_unix.empty() || !run_unix(L"/bin/bash \"" + helper_unix + L"\"")) return false;

    if (desktop_unix) {
        std::string p = read_text_file(g.demo + L"\\GhostRecomp-launch.path");
        while (!p.empty() && (p.back() == '\n' || p.back() == '\r')) p.pop_back();
        *desktop_unix = widen(p);
    }
    return true;
}

static bool run_unix(const std::wstring &args)
{
    std::wstring cmd = L"start.exe /unix " + args;
    std::vector<wchar_t> buf(cmd.begin(), cmd.end());
    buf.push_back(0);
    STARTUPINFOW si = {};
    si.cb = sizeof(si);
    PROCESS_INFORMATION pi = {};
    if (!CreateProcessW(NULL, buf.data(), NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi))
        return false;
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return true;
}

static void launch_game()
{
    save_settings();
    if (running_under_wine() && provision_launcher(NULL)) {
        if (run_unix(L"/usr/bin/gtk-launch scghost-recompiled")) return;
        std::wstring script_unix = unix_from_win(g.demo + L"\\GhostRecomp-launch.sh");
        if (!script_unix.empty() && run_unix(L"/bin/bash \"" + script_unix + L"\"")) return;
    }

    std::wstring exe = g.demo + L"\\GhostRecomp.exe";
    std::wstring params = std::wstring(L"--resolution=") + kResArg[g.res_index];
    if (g.input_kbm) params += L" --kbm";
    SetEnvironmentVariableW(L"SCGHOST_SHADOW_TEX", g.shadow_high ? L"1024" : L"512");
    SHELLEXECUTEINFOW si = {};
    si.cbSize = sizeof(si);
    si.lpFile = exe.c_str();
    si.lpParameters = params.c_str();
    si.lpDirectory = g.demo.c_str();
    si.nShow = SW_SHOWNORMAL;
    ShellExecuteExW(&si);
    SetEnvironmentVariableW(L"SCGHOST_SHADOW_TEX", NULL);
}

static void play_game()
{
    save_settings();
    launch_game();
    PostQuitMessage(0);
}

static void activate_menu()
{
    if (g.menu < 0 || !menu_id_visible(g.menu)) return;
    switch (g.menu) {
    case 0: case 1: goto_page(PAGE_LOCATE); break;
    case 2:
        if (!g.installed) MessageBoxW(g.hwnd, L"Nothing to remove.", kTitle, MB_ICONINFORMATION);
        else goto_page(PAGE_REMOVE);
        break;
    case 3: goto_page(PAGE_ABOUT); break;
    case 4: PostQuitMessage(0); break;
    case 5: if (g.installed) goto_page(PAGE_LAUNCH); break;
    }
}

static void on_next()
{
    read_options();
    if (g.page == PAGE_LOCATE) {
        if (!g.demo_ok) {
            MessageBoxW(g.hwnd, g.status.c_str(), kTitle, MB_ICONERROR);
            return;
        }
        goto_page(PAGE_OPTIONS);
    } else if (g.page == PAGE_OPTIONS) {
        start_install();
    } else if (g.page == PAGE_FINISH) {
        if (!g.failed && g.opt_launch) launch_game();
        PostQuitMessage(0);
    } else if (g.page == PAGE_ABOUT) {
        goto_page(PAGE_MENU);
    } else if (g.page == PAGE_REMOVE) {
        if (remove_install()) goto_page(PAGE_MENU);
    }
}

static void on_back()
{
    if (g.busy) return;
    if (g.page == PAGE_OPTIONS) goto_page(PAGE_LOCATE);
    else goto_page(PAGE_MENU);
}

static int menu_hit(int x, int y)
{
    if (x < kMenuX) return -1;
    if (y >= 168 && y < 215) return 0;
    if (y >= 220 && y < 220 + 2 * kMenuH) return 1 + (y - 220) / kMenuH;
    if (y >= 315 && y < 355) return 3;
    if (y >= 421 && y < 453) {
        if (g.installed && x >= 320) return 5;
        return 4;
    }
    return -1;
}

static LRESULT CALLBACK wnd_proc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
    switch (msg) {
    case WM_PAINT: paint(hwnd); return 0;
    case WM_ERASEBKGND: return 1;
    case WM_LBUTTONDOWN:
        if (sound_hit(LOWORD(lp), HIWORD(lp))) {
            toggle_sound();
            InvalidateRect(hwnd, NULL, FALSE);
            return 0;
        }
        if (g.page == PAGE_MENU) {
            int i = menu_hit(LOWORD(lp), HIWORD(lp));
            if (i >= 0 && i < kMenuN && menu_id_visible(i)) { g.menu = i; activate_menu(); }
        } else if (g.page == PAGE_LAUNCH) {
            int x = LOWORD(lp), y = HIWORD(lp);
            if (x >= 270 && x < 620 && y >= 421 && y < 461) play_game();
        }
        return 0;
    case WM_MOUSEMOVE:
        if (g.page == PAGE_MENU) {
            int i = menu_hit(LOWORD(lp), HIWORD(lp));
            if (i >= 0 && i < kMenuN && menu_id_visible(i)) {
                if (i != g.menu) { g.menu = i; InvalidateRect(hwnd, NULL, FALSE); }
            } else if (g.menu != -1) {
                g.menu = -1;
                InvalidateRect(hwnd, NULL, FALSE);
            }
        } else if (g.page == PAGE_LAUNCH) {
            int x = LOWORD(lp), y = HIWORD(lp);
            int want = (x >= 270 && x < 620 && y >= 421 && y < 461) ? 100 : -1;
            if (want != g.menu) { g.menu = want; InvalidateRect(hwnd, NULL, FALSE); }
        }
        return 0;
    case WM_KEYDOWN:
        if (g.page == PAGE_MENU) {
            if (wp == VK_DOWN) menu_step(1);
            else if (wp == VK_UP) menu_step(-1);
            else if (wp == VK_RETURN) { activate_menu(); return 0; }
            else if (wp == VK_ESCAPE) { PostQuitMessage(0); return 0; }
            else if (wp == 'I') { g.menu = 0; activate_menu(); return 0; }
            else if (wp == 'F' && g.installed) { g.menu = 1; activate_menu(); return 0; }
            else if (wp == 'M' && g.installed) { g.menu = 2; activate_menu(); return 0; }
            else if (wp == 'A') { g.menu = 3; activate_menu(); return 0; }
            else if (wp == 'X') { g.menu = 4; activate_menu(); return 0; }
            else if (wp == 'N' && g.installed) { g.menu = 5; activate_menu(); return 0; }
            InvalidateRect(hwnd, NULL, FALSE);
        } else if (g.page == PAGE_LAUNCH) {
            if (wp == 'Y' || wp == VK_RETURN) { play_game(); return 0; }
            if (wp == VK_ESCAPE) on_back();
        } else if (wp == VK_ESCAPE) on_back();
        return 0;
    case WM_COMMAND:
        if ((HWND)lp == g.btn_browse) browse();
        else if ((HWND)lp == g.btn_next) on_next();
        else if ((HWND)lp == g.btn_back) on_back();
        else if ((HWND)lp == g.btn_cancel) {
            if (g.busy) g.cancel = true;
            else PostQuitMessage(0);
        } else if ((HWND)lp == g.btn_details) toggle_log();
        else if ((HWND)lp == g.cb_res && HIWORD(wp) == CBN_SELCHANGE) {
            int v = (int)SendMessageW(g.cb_res, CB_GETCURSEL, 0, 0);
            if (v >= 0 && v < 4) { g.res_index = v; save_settings(); }
        } else if ((HWND)lp == g.chk_shadow) {
            g.shadow_high = SendMessageW(g.chk_shadow, BM_GETCHECK, 0, 0) == BST_CHECKED;
            save_settings();
        } else if ((HWND)lp == g.cb_input && HIWORD(wp) == CBN_SELCHANGE) {
            int v = (int)SendMessageW(g.cb_input, CB_GETCURSEL, 0, 0);
            if (v >= 0) { g.input_kbm = v == 1; save_settings(); }
        }
        return 0;
    case WM_APP + 1:
        InvalidateRect(hwnd, NULL, FALSE);
        return 0;
    case WM_APP + 2:
        g.busy = false;
        EnableWindow(g.btn_next, TRUE);
        save_log_file();
        goto_page(PAGE_FINISH);
        return 0;
    case WM_CLOSE:
        if (g.busy) g.cancel = true;
        else PostQuitMessage(0);
        return 0;
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

static HWND make_btn(const wchar_t *text, int x, int y, int w, int h, HMENU id)
{
    HWND b = CreateWindowExW(0, L"BUTTON", text, WS_CHILD | WS_TABSTOP | BS_PUSHBUTTON,
        x, y, w, h, g.hwnd, id, GetModuleHandleW(NULL), NULL);
    SendMessageW(b, WM_SETFONT, (WPARAM)g.font_body, TRUE);
    return b;
}

static HWND make_chk(const wchar_t *text, int y)
{
    HWND b = CreateWindowExW(0, L"BUTTON", text, WS_CHILD | WS_TABSTOP | BS_AUTOCHECKBOX,
        kMenuX, y, 360, 22, g.hwnd, NULL, GetModuleHandleW(NULL), NULL);
    SendMessageW(b, WM_SETFONT, (WPARAM)g.font_body, TRUE);
    return b;
}

static HFONT make_font(int h)
{
    const int PCT = 85;
    HDC sdc = CreateCompatibleDC(NULL);
    HFONT probe = CreateFontW(-h, 0, 0, 0, FW_NORMAL, 0, 0, 0, DEFAULT_CHARSET, 0, 0, ANTIALIASED_QUALITY, 0, L"Eurostile");
    HFONT old = (HFONT)SelectObject(sdc, probe);
    TEXTMETRICW tm = {};
    GetTextMetricsW(sdc, &tm);
    int w = tm.tmAveCharWidth;
    SelectObject(sdc, old);
    DeleteObject(probe);
    DeleteDC(sdc);
    return CreateFontW(-(h * PCT / 100), w, 0, 0, FW_NORMAL, 0, 0, 0, DEFAULT_CHARSET, 0, 0, ANTIALIASED_QUALITY, 0, L"Eurostile");
}

static int run_ui()
{
    GdiplusStartupInput in;
    GdiplusStartup(&g.gdip, &in, NULL);
    detect();
    load_settings();
    load_font_mem();
    load_splashes();
    start_music();
    g.font_title = make_font(38);
    g.font_menu = make_font(22);
    g.font_body = make_font(21);
    g.font_small = make_font(17);

    WNDCLASSW wc = {};
    wc.lpfnWndProc = wnd_proc;
    wc.hInstance = GetModuleHandleW(NULL);
    wc.lpszClassName = L"SGSetup";
    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)GetStockObject(BLACK_BRUSH);
    RegisterClassW(&wc);

    RECT wr = {0, 0, kW, kH};
    AdjustWindowRect(&wr, WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX, FALSE);
    g.hwnd = CreateWindowExW(0, L"SGSetup", kTitle,
        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
        CW_USEDEFAULT, CW_USEDEFAULT, wr.right - wr.left, wr.bottom - wr.top,
        NULL, NULL, wc.hInstance, NULL);

    g.ed_path = CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"",
        WS_CHILD | WS_TABSTOP | ES_AUTOHSCROLL, kMenuX, 190, 460, 24, g.hwnd, NULL, wc.hInstance, NULL);
    SendMessageW(g.ed_path, WM_SETFONT, (WPARAM)g.font_body, TRUE);
    g.btn_browse = make_btn(L"Browse...", 500, 188, 110, 26, (HMENU)1);
    g.chk_desk = make_chk(L"Create desktop shortcut", 200);
    g.chk_start = make_chk(L"Create Start Menu shortcut", 230);
    g.chk_launch = make_chk(L"Launch after installation", 260);
    g.cb_res = CreateWindowExW(0, L"COMBOBOX", L"",
        WS_CHILD | WS_TABSTOP | WS_VSCROLL | CBS_DROPDOWNLIST,
        120, 194, 180, 200, g.hwnd, NULL, wc.hInstance, NULL);
    SendMessageW(g.cb_res, WM_SETFONT, (WPARAM)g.font_body, TRUE);
    for (int i = 0; i < 4; i++)
        SendMessageW(g.cb_res, CB_ADDSTRING, 0, (LPARAM)kResSel[i]);
    SendMessageW(g.cb_res, CB_SETCURSEL, g.res_index, 0);
    g.chk_shadow = CreateWindowExW(0, L"BUTTON", L"High-resolution shadows",
        WS_CHILD | WS_TABSTOP | BS_AUTOCHECKBOX, kMenuX, 266, 380, 22, g.hwnd, NULL, wc.hInstance, NULL);
    SendMessageW(g.chk_shadow, WM_SETFONT, (WPARAM)g.font_body, TRUE);
    g.cb_input = CreateWindowExW(0, L"COMBOBOX", L"",
        WS_CHILD | WS_TABSTOP | WS_VSCROLL | CBS_DROPDOWNLIST,
        120, 296, 220, 200, g.hwnd, NULL, wc.hInstance, NULL);
    SendMessageW(g.cb_input, WM_SETFONT, (WPARAM)g.font_body, TRUE);
    SendMessageW(g.cb_input, CB_ADDSTRING, 0, (LPARAM)L"Gamepad");
    SendMessageW(g.cb_input, CB_ADDSTRING, 0, (LPARAM)L"Keyboard + mouse");
    SendMessageW(g.cb_input, CB_SETCURSEL, g.input_kbm ? 1 : 0, 0);
    g.btn_back = make_btn(L"< Back", kMenuX, 430, 90, 28, (HMENU)2);
    g.btn_next = make_btn(L"Next >", 400, 430, 110, 28, (HMENU)3);
    g.btn_cancel = make_btn(L"Cancel", 520, 430, 90, 28, (HMENU)4);
    g.btn_details = make_btn(L"Details >>", 180, 430, 110, 28, (HMENU)5);
    layout_controls();
    ShowWindow(g.hwnd, SW_SHOW);
    UpdateWindow(g.hwnd);

    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0)) {
        if (IsDialogMessageW(g.hwnd, &msg)) continue;
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    stop_music();
    if (g.fontmem) RemoveFontMemResourceEx(g.fontmem);
    if (g.map) CloseHandle(g.map);
    for (int i = 0; i < SPL_COUNT; i++) delete g.splash[i];
    delete g.logo;
    GdiplusShutdown(g.gdip);
    return (int)msg.wParam;
}

static int run_quiet(const std::wstring &dir)
{
    g.demo = dir;
    set_status();
    if (!g.demo_ok) {
        fwprintf(stderr, L"invalid demo folder: %s\n", dir.c_str());
        return 2;
    }
    g.opt_desktop = false;
    g.opt_start = false;
    g.opt_launch = false;
    g.hwnd = NULL;
    install_thread(NULL);
    fwprintf(stderr, L"%s\n", g.failed ? L"FAIL" : L"OK");
    return g.failed ? 1 : 0;
}

int WINAPI wWinMain(HINSTANCE, HINSTANCE, LPWSTR, int)
{
    int argc = 0;
    LPWSTR *argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    std::wstring quiet_dir;
    for (int i = 1; i < argc; i++) {
        if (!wcscmp(argv[i], L"--quiet") && i + 1 < argc) quiet_dir = argv[++i];
    }
    LocalFree(argv);
    if (!load_payload()) {
        MessageBoxW(NULL, L"This installer package is damaged or incomplete.", kTitle, MB_ICONERROR);
        return 1;
    }
    CoInitializeEx(NULL, COINIT_APARTMENTTHREADED);
    int rc = quiet_dir.empty() ? run_ui() : run_quiet(quiet_dir);
    CoUninitialize();
    return rc;
}
