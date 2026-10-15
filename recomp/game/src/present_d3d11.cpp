/**
 * Optional D3D11/DXGI presenter for the guest framebuffer.
 *
 * The default presenter is the GDI window in the runtime
 * (refs/xboxrecomp/src/video/fb_present.c): the pushbuffer executor copies each
 * finished frame into a double buffer and the window thread blits it with
 * StretchDIBits. That is enough to see the game, but StretchDIBits has no swap
 * chain for a post-processing injector such as ReShade to hook -- ReShade hooks
 * IDXGISwapChain::Present and the DXGI factory, and a GDI blit is neither.
 *
 * This module gives the same window a real D3D11 swap chain so ReShade (loaded
 * as a dxgi.dll proxy) has something to hook. It is opt-in: the game installs
 * it only when RECOMP_PRESENT=d3d11 (see src/main.c). When installed, the
 * runtime suspends its GDI blit (xbox_FramebufferWindowSuspend) so the two do
 * not fight over the HWND; message pumping, input, recording/replay, the F12
 * dump and the window-title FPS counter all keep working.
 *
 * The frame arrives through xbox_SetPresentHook, called synchronously at the
 * flip, so the guest memory it points at is stable for the whole upload.
 *
 * No shaders: the converted pixels are 0x00RRGGBB (byte order B,G,R,A), which
 * is exactly DXGI_FORMAT_B8G8R8A8_UNORM, so one CopyResource to the back buffer
 * is the whole draw. ReShade runs its effect chain later, on Present.
 */

#include <windows.h>
#include <d3d11.h>
#include <dxgi.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

extern "C" ptrdiff_t xbox_GetMemoryOffset(void);
extern "C" int xbox_GammaRampGet(uint8_t *out);
/* Declared in refs/xboxrecomp/src/video/video_player.h; re-declared here so the
 * game source does not depend on the runtime's private include path. */
extern "C" void xbox_SetPresentHook(void (*hook)(uint32_t, uint32_t, void *),
                                    void *user);
extern "C" int xbox_FramebufferWindowSize(uint32_t *width, uint32_t *height);
/* The emulator's native D3D11 device (refs/xboxrecomp/src/kernel/nv2a_gpu.h). */
extern "C" void *nv2a_gpu_device(void);

static ID3D11Device        *s_dev;
static ID3D11DeviceContext *s_ctx;
static IDXGISwapChain      *s_swap;
static ID3D11Texture2D     *s_upload;
static uint32_t             s_w = 640, s_h = 480;
static int                  s_failed;
static int                  s_logged;

/* Per-channel display gamma, refreshed from the guest's DAC palette each frame,
 * mirroring fb_present.c so the picture matches the GDI path. */
static uint8_t s_gr[256], s_gg[256], s_gb[256];
static int     s_gamma_identity = 1;

static void gamma_refresh(void)
{
    uint8_t ramp[256 * 3];
    int i;

    if (!xbox_GammaRampGet(ramp)) {
        s_gamma_identity = 1;
        return;
    }
    for (i = 0; i < 256; i++) {
        s_gr[i] = ramp[i * 3 + 0];
        s_gg[i] = ramp[i * 3 + 1];
        s_gb[i] = ramp[i * 3 + 2];
    }
    s_gamma_identity = 0;
}

/* Returns 1 on success, 0 when the window is not up yet (retry next flip), and
 * -1 on a fatal D3D failure (the caller restores the GDI path). */
static int present_init(void)
{
    HWND hwnd;
    RECT rc = {0, 0, 0, 0};
    uint32_t fw = 0, fh = 0;
    DXGI_SWAP_CHAIN_DESC sd;
    D3D11_TEXTURE2D_DESC td;
    HRESULT hr;

    /* The window is created by the runtime's fb_thread (class
     * "XboxRecompFramebuffer"); flips only start once it exists, but retry
     * cheaply if this callback somehow arrives first. */
    hwnd = FindWindowA("XboxRecompFramebuffer", NULL);
    if (!hwnd)
        return 0;

    /* Size to the title's render resolution, not the client rect: the frame's
     * pitch is bytes-per-row for that width. DXGI scales the back buffer to
     * whatever the window client area is. */
    if (xbox_FramebufferWindowSize(&fw, &fh) && fw && fh) {
        s_w = fw;
        s_h = fh;
    } else if (GetClientRect(hwnd, &rc) && rc.right > rc.left && rc.bottom > rc.top) {
        s_w = (uint32_t)(rc.right - rc.left);
        s_h = (uint32_t)(rc.bottom - rc.top);
    } else {
        s_w = 640;
        s_h = 480;
    }
    fprintf(stderr, "[PRESENT] fb %ux%u, client %ldx%ld\n",
            s_w, s_h, (long)(rc.right - rc.left), (long)(rc.bottom - rc.top));

    memset(&sd, 0, sizeof sd);
    sd.BufferDesc.Width  = s_w;
    sd.BufferDesc.Height = s_h;
    sd.BufferDesc.Format = DXGI_FORMAT_B8G8R8A8_UNORM;
    sd.BufferDesc.RefreshRate.Numerator   = 60;
    sd.BufferDesc.RefreshRate.Denominator = 1;
    sd.SampleDesc.Count = 1;
    sd.BufferUsage      = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    sd.BufferCount      = 2;
    sd.OutputWindow     = hwnd;
    sd.Windowed         = TRUE;
    sd.SwapEffect       = DXGI_SWAP_EFFECT_DISCARD;

    /* Prefer the emulator's own D3D11 device so the swap chain shares its
     * immediate context/queue with the scene draws. ReShade's Generic Depth
     * associates a depth-stencil resource with the Present that follows its
     * draws on the same queue; a private device would Present on a queue that
     * never saw the scene depth, so depth-based effects found nothing (and
     * DisplayDepth crashed). Fall back to a private device if the runtime has
     * not created one yet (it is created lazily on first GPU work). */
    {
        ID3D11Device *shared = (ID3D11Device *)nv2a_gpu_device();
        if (shared) {
            IDXGIDevice *dxgi_dev = NULL;
            IDXGIAdapter *adapter = NULL;
            IDXGIFactory *factory = NULL;
            HRESULT q = shared->QueryInterface(IID_IDXGIDevice, (void **)&dxgi_dev);
            if (SUCCEEDED(q))
                q = dxgi_dev->GetAdapter(&adapter);
            if (SUCCEEDED(q))
                q = adapter->GetParent(IID_IDXGIFactory, (void **)&factory);
            if (SUCCEEDED(q))
                q = factory->CreateSwapChain((IUnknown *)shared, &sd, &s_swap);
            if (factory) factory->Release();
            if (adapter) adapter->Release();
            if (dxgi_dev) dxgi_dev->Release();
            if (FAILED(q)) {
                fprintf(stderr, "[PRESENT] swap chain on emulator device failed: 0x%08lX\n",
                        (unsigned long)q);
                return -1;
            }
            s_dev = shared;
            s_dev->AddRef();
            s_dev->GetImmediateContext(&s_ctx);
            fprintf(stderr, "[PRESENT] using emulator D3D11 device (shared queue)\n");
        } else {
            hr = D3D11CreateDeviceAndSwapChain(
                NULL, D3D_DRIVER_TYPE_HARDWARE, NULL, 0, NULL, 0,
                D3D11_SDK_VERSION, &sd, &s_swap, &s_dev, NULL, &s_ctx);
            if (FAILED(hr)) {
                fprintf(stderr, "[PRESENT] D3D11CreateDeviceAndSwapChain failed: 0x%08lX\n",
                        (unsigned long)hr);
                return -1;
            }
            fprintf(stderr, "[PRESENT] using private D3D11 device\n");
        }
    }

    memset(&td, 0, sizeof td);
    td.Width            = s_w;
    td.Height           = s_h;
    td.MipLevels        = 1;
    td.ArraySize        = 1;
    td.Format           = DXGI_FORMAT_B8G8R8A8_UNORM;
    td.SampleDesc.Count = 1;
    td.Usage            = D3D11_USAGE_DYNAMIC;
    td.BindFlags        = 0;
    td.CPUAccessFlags   = D3D11_CPU_ACCESS_WRITE;
    hr = s_dev->CreateTexture2D(&td, NULL, &s_upload);
    if (FAILED(hr)) {
        fprintf(stderr, "[PRESENT] CreateTexture2D failed: 0x%08lX\n",
                (unsigned long)hr);
        return -1;
    }

    fprintf(stderr, "[PRESENT] d3d11 swap chain ready (%ux%u)\n", s_w, s_h);
    return 1;
}

static void present_frame(uint32_t fb_va, uint32_t pitch, void *user)
{
    uint32_t bpp, x, y;
    const uint8_t *src;
    D3D11_MAPPED_SUBRESOURCE map;
    ID3D11Texture2D *back = NULL;

    (void)user;
    if (s_failed)
        return;
    if (!s_dev) {
        int r = present_init();
        if (r == 0)
            return;                 /* window not up yet; try next flip */
        if (r < 0) {
            /* Cannot present in D3D11 at all: hand the window back to GDI so
             * the run still shows a picture. */
            s_failed = 1;
            xbox_SetPresentHook(NULL, NULL);
            return;
        }
    }
    if (!fb_va || !pitch)
        return;

    bpp = pitch / s_w;
    src = (const uint8_t *)xbox_GetMemoryOffset() + fb_va;

    if (!s_logged) {
        s_logged = 1;
        fprintf(stderr, "[PRESENT] first frame 0x%08X pitch %u bpp %u\n",
                fb_va, pitch, bpp);
    }

    gamma_refresh();

    if (FAILED(s_ctx->Map(s_upload, 0, D3D11_MAP_WRITE_DISCARD, 0, &map))) {
        fprintf(stderr, "[PRESENT] Map failed; the GDI presenter resumes\n");
        s_failed = 1;
        xbox_SetPresentHook(NULL, NULL);
        return;
    }

    for (y = 0; y < s_h; y++) {
        const uint8_t *row = src + (size_t)y * pitch;
        uint8_t *dst = (uint8_t *)map.pData + (size_t)y * map.RowPitch;

        if (bpp == 4) {
            const uint32_t *p = (const uint32_t *)row;
            for (x = 0; x < s_w; x++) {
                uint32_t v = p[x];
                if (!s_gamma_identity) {
                    v = ((uint32_t)s_gr[(v >> 16) & 0xFF] << 16) |
                        ((uint32_t)s_gg[(v >>  8) & 0xFF] <<  8) |
                         (uint32_t)s_gb[ v        & 0xFF];
                }
                ((uint32_t *)dst)[x] = v;
            }
        } else if (bpp == 2) {
            const uint16_t *p = (const uint16_t *)row;
            for (x = 0; x < s_w; x++) {
                uint16_t v = p[x];
                uint32_t r = (uint32_t)((v >> 11) & 0x1F) * 255u / 31u;
                uint32_t g = (uint32_t)((v >>  5) & 0x3F) * 255u / 63u;
                uint32_t b = (uint32_t)( v        & 0x1F) * 255u / 31u;
                if (!s_gamma_identity) {
                    r = s_gr[r];
                    g = s_gg[g];
                    b = s_gb[b];
                }
                ((uint32_t *)dst)[x] = (r << 16) | (g << 8) | b;
            }
        } else {
            memset(dst, 0, (size_t)s_w * 4);
        }
    }
    s_ctx->Unmap(s_upload, 0);

    if (FAILED(s_swap->GetBuffer(0, IID_ID3D11Texture2D, (void **)&back)))
        return;
    s_ctx->CopyResource(back, s_upload);
    back->Release();
    s_swap->Present(1, 0);
}

extern "C" void xbox_PresentD3D11Install(void)
{
    xbox_SetPresentHook(present_frame, NULL);
}