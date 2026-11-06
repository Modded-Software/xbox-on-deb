/* WinMain -> wWinMain bridge for the 32-bit XP installer build.
 *
 * The normal build links with -municode so the CRT calls wWinMain directly.
 * The XP toolchain (zig 0.11, msvcrt instead of the UCRT) rejects -municode,
 * so the x86 build links a plain GUI subsystem entry and forwards here.
 * The wide command line comes from GetCommandLineW(), which is what the
 * installer reads anyway.
 */
#include <windows.h>

int WINAPI wWinMain(HINSTANCE, HINSTANCE, LPWSTR, int);

int WINAPI WinMain(HINSTANCE inst, HINSTANCE prev, LPSTR cmdline, int show)
{
    (void)cmdline;
    return wWinMain(inst, prev, GetCommandLineW(), show);
}
