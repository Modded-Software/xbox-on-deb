#include <windows.h>
#include <shellapi.h>
#include <shlobj.h>
#include <stdio.h>
#include <string>
#include <vector>

static std::wstring exe_dir()
{
    wchar_t buf[MAX_PATH];
    GetModuleFileNameW(NULL, buf, MAX_PATH);
    wchar_t *slash = wcsrchr(buf, L'\\');
    if (slash) *slash = 0;
    return buf;
}

static std::string narrow(const std::wstring &w)
{
    int n = WideCharToMultiByte(CP_UTF8, 0, w.c_str(), -1, NULL, 0, NULL, NULL);
    std::string s(n ? n - 1 : 0, 0);
    if (n) WideCharToMultiByte(CP_UTF8, 0, w.c_str(), -1, &s[0], n, NULL, NULL);
    return s;
}

static std::wstring widen(const std::string &s)
{
    int n = MultiByteToWideChar(CP_UTF8, 0, s.c_str(), -1, NULL, 0);
    std::wstring w(n ? n - 1 : 0, 0);
    if (n) MultiByteToWideChar(CP_UTF8, 0, s.c_str(), -1, &w[0], n);
    return w;
}

static std::vector<std::string> read_manifest(const std::wstring &path)
{
    std::vector<std::string> lines;
    HANDLE h = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) return lines;
    DWORD sz = GetFileSize(h, NULL);
    std::string data(sz, 0);
    DWORD n = 0;
    ReadFile(h, &data[0], sz, &n, NULL);
    CloseHandle(h);
    data.resize(n);
    size_t i = 0;
    while (i < data.size()) {
        size_t j = data.find_first_of("\r\n", i);
        if (j == std::string::npos) j = data.size();
        if (j > i) lines.push_back(data.substr(i, j - i));
        i = j + 1;
    }
    return lines;
}

static void del_reg(const std::wstring &key)
{
    if (key.rfind(L"HKCU\\", 0) != 0) return;
    RegDeleteKeyW(HKEY_CURRENT_USER, key.c_str() + 5);
}

static int do_remove(const std::wstring &dir, bool quiet)
{
    if (!quiet) {
        int r = MessageBoxW(NULL,
            L"Remove StarCraft: Ghost Recompiled?\n\n"
            L"Only the recompiled runtime, shortcuts, and uninstall entry are removed.\n"
            L"The original demo files are left alone.",
            L"StarCraft: Ghost Recompiled", MB_YESNO | MB_ICONQUESTION);
        if (r != IDYES) return 0;
    }
    auto lines = read_manifest(dir + L"\\GhostRecomp.manifest");
    std::wstring self = dir + L"\\GhostRecomp-Uninstall.exe";
    for (auto &ln : lines) {
        if (ln.rfind("file=", 0) == 0) {
            std::wstring p = dir + L"\\" + widen(ln.substr(5));
            if (_wcsicmp(p.c_str(), self.c_str()) != 0) DeleteFileW(p.c_str());
        } else if (ln.rfind("shortcut=", 0) == 0) {
            DeleteFileW(widen(ln.substr(9)).c_str());
        } else if (ln.rfind("unixfile=", 0) == 0) {
            std::wstring p = widen(ln.substr(9));
            if (!p.empty() && p[0] == L'/') p = L"Z:" + p;
            DeleteFileW(p.c_str());
        } else if (ln.rfind("reg=", 0) == 0) {
            del_reg(widen(ln.substr(4)));
        }
    }
    for (auto &ln : lines) {
        if (ln.rfind("dir=", 0) == 0)
            RemoveDirectoryW(widen(ln.substr(4)).c_str());
    }
    DeleteFileW((dir + L"\\GhostRecomp.manifest").c_str());
    DeleteFileW((dir + L"\\GhostRecomp-install.log").c_str());
    MoveFileExW(self.c_str(), NULL, MOVEFILE_DELAY_UNTIL_REBOOT);
    if (!quiet)
        MessageBoxW(NULL, L"StarCraft: Ghost Recompiled has been removed.",
                    L"StarCraft: Ghost Recompiled", MB_OK | MB_ICONINFORMATION);
    return 0;
}

int WINAPI wWinMain(HINSTANCE, HINSTANCE, LPWSTR, int)
{
    int argc = 0;
    LPWSTR *argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    bool quiet = false;
    for (int i = 1; i < argc; i++)
        if (!wcscmp(argv[i], L"/quiet") || !wcscmp(argv[i], L"--quiet")) quiet = true;
    LocalFree(argv);
    return do_remove(exe_dir(), quiet);
}
