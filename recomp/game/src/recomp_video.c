/**
 * StarCraft: Ghost render-resolution override.
 *
 * The title picks its render size in tRenderOptions::tRenderOptions
 * (guest VA 0x001F0490) from two inputs, then writes a global render-options
 * object at guest VA 0x49E630 (width +0x74/+0x78, height +0x72/+0x76, mode
 * index +0x7C) and snapshots it into the engine via
 * renderMain_SetScreenResolution:
 *
 *   - XGetVideoFlags(): EEPROM setting XC_VIDEO, read as (value >> 16) & 0x5F.
 *       bit 0 = widescreen, bit 1 = width >= 1280, bit 2 = width >= 1920.
 *   - XGetAVPack(): returns *(*(0x361908)); the constructor only takes its
 *       720p branch when that equals 1.
 *
 * The actual NV2A mode/timings come from a built-in table keyed on the word
 * AvSendTVEncoderOption(QUERY_AVPACK) returns: each table row is
 * {av_info, resolution, mode_word}, and the row selected is the one whose
 * av_info matches that word. So a resolution only holds if the flags, the
 * XGetAVPack cell and the AV word all agree with the same row.
 *
 * Two mechanisms, both driven by RECOMP_RESOLUTION:
 *   - mechanism 1 (native modes 640x480 / 720x480 / 1280x720): steer the flags
 *     and the XGetAVPack cell so the constructor chooses the mode itself.
 *   - mechanism 2 (any other size, or RECOMP_RESOLUTION_EXACT=1): also rewrite
 *     the render-options fields directly, with the AV word selecting the table
 *     row that carries that resolution.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

#include "recomp_types.h"

#define SCGHOST_RENDER_OPTIONS_VA 0x49E630u
#define ROPT_WIDTH_A              0x74u   /* engine copy */
#define ROPT_WIDTH_B              0x78u   /* present-params copy */
#define ROPT_HEIGHT_A             0x72u
#define ROPT_HEIGHT_B             0x76u
#define ROPT_MODE_INDEX           0x7Cu   /* 0=480i, 4=widescreen, 5=720p */
#define XC_VIDEO_INDEX            0x08u

/* XGetAVPack (0x2AE023) returns MEM32(MEM32(0x361908)); the runtime rewrites
 * that cell to a game global, so follow the pointer. */
#define XGETAVPACK_PTR_VA         0x361908u

/* AV-info words from the title's display-mode table (guest 0x2D03E8), indexed
 * by the resolution they carry. The high byte selects which row is used. */
#define AVWORD_640x480            0x00400104u
#define AVWORD_720x480            0x00480104u
#define AVWORD_1280x720           0x00430104u
/* The title's own 1920x1080 row is 0x00650104: byte2 bit5 (0x20) is the
 * interlace/component flag, which makes the present path treat the frame as
 * 1080i (field presentation, padded stride). Clear it so the row reads as a
 * progressive 1080 (byte2 0x65 -> 0x45); the row is rewritten at runtime by
 * scghost_patch_mode_table(). */
#define AVWORD_1920x1080          0x00450104u

/* The title's built-in display-mode table lives at guest VA 0x2D03E8: rows of
 * {u32 av_info, u32 packed_wh (lo16=w, hi16=h), u32 mode_word}. */
#define DISPLAYMODE_TABLE_VA      0x2D03E8u
#define DISPLAYMODE_TABLE_LEN     0x8ACu
#define DISPLAYMODE_ROW_BYTES     0xCu

extern int  xbox_VideoDesiredResolution(uint32_t *width, uint32_t *height);
extern void xbox_VideoSetQueryHook(void (*hook)(uint32_t value_index, uint32_t *value, int *handled));
extern void xbox_VideoSetAvPackHook(void (*hook)(uint32_t *value));

static void scghost_patch_mode_table(void);

static uint32_t scghost_avword(uint32_t w, uint32_t h)
{
    if (w >= 1920 || h >= 1080)
        return AVWORD_1920x1080;
    if (w >= 1280 || h >= 720)
        return AVWORD_1280x720;
    if (w > 640 || h > 480)
        return AVWORD_720x480;
    return AVWORD_640x480;
}

/* Mechanism 1 needs this to be 1 for the 720p branch of the constructor. */
static void scghost_set_hd_boot_mode(uint32_t on)
{
    uint32_t cell = MEM32(XGETAVPACK_PTR_VA);

    if (cell)
        MEM32(cell) = on;
}

/* Pick the AV-info word that owns the table row for the requested resolution. */
static void scghost_avpack(uint32_t *value)
{
    uint32_t w, h;

    if (xbox_VideoDesiredResolution(&w, &h))
        *value = scghost_avword(w, h);
}

static void scghost_video_query(uint32_t value_index, uint32_t *value, int *handled)
{
    const char *exact_env = getenv("RECOMP_RESOLUTION_EXACT");
    int exact = exact_env && exact_env[0] && exact_env[0] != '0';
    int native;
    uint32_t w, h;

    if (value_index != XC_VIDEO_INDEX)
        return;
    if (!xbox_VideoDesiredResolution(&w, &h))
        return;

    /* First query runs well after the XBE image is mapped, so the display-mode
     * table is live; patch the 1080 row once. */
    scghost_patch_mode_table();

    native = (w == 640 && h == 480) || (w == 720 && h == 480) ||
             (w == 1280 && h == 720);

    if (exact || !native) {
        /* Mechanism 2: write the exact size into the title's own options and
         * keep the constructor off them. The AV word above makes the mode row
         * agree, so the device comes up at this size. */
        MEM16(SCGHOST_RENDER_OPTIONS_VA + ROPT_WIDTH_A)  = (uint16_t)w;
        MEM16(SCGHOST_RENDER_OPTIONS_VA + ROPT_WIDTH_B)  = (uint16_t)w;
        MEM16(SCGHOST_RENDER_OPTIONS_VA + ROPT_HEIGHT_A) = (uint16_t)h;
        MEM16(SCGHOST_RENDER_OPTIONS_VA + ROPT_HEIGHT_B) = (uint16_t)h;
        MEM8(SCGHOST_RENDER_OPTIONS_VA + ROPT_MODE_INDEX) =
            (uint8_t)((w >= 1280 || h >= 720) ? 5 : (w > 640 || h > 480) ? 4 : 0);
        *value = 0;
        fprintf(stderr, "  [VIDEO] exact render options %ux%u (avword=%08X)\n",
                (unsigned)w, (unsigned)h, (unsigned)scghost_avword(w, h));
    } else {
        /* Mechanism 1: let the constructor pick the native mode. */
        if (w >= 1280 || h >= 720) {
            *value = 0x02u << 16;      /* width >= 1280 -> 720p branch */
            scghost_set_hd_boot_mode(1);
        } else if (w > 640 || h > 480) {
            *value = 0x01u << 16;      /* widescreen -> 720x480 branch */
        } else {
            *value = 0;
        }
        fprintf(stderr, "  [VIDEO] native mode %ux%u (flags=%08X avword=%08X)\n",
                (unsigned)w, (unsigned)h, (unsigned)*value,
                (unsigned)scghost_avword(w, h));
    }
    if (handled)
        *handled = 1;
    fflush(stderr);
}

/* Display gamma (in-game brightness slider).
 *
 * tRenderOptions::SetUserBrightness -> rlMain_SetGamma -> D3DDevice_SetGammaRamp
 * (0x2C1BD0, flags 0). SetGammaRamp copies the ramp into one of two shadow
 * buffers in the D3D miniport (g_pMiniport = MEM32(0x2D2148)), records which
 * one is current, and only marks it dirty; the DAC is reprogrammed later by
 * CMiniport::ServiceQueuedFlips, and only when a queued flip retires on the
 * buffer parity that matches. In the recompiled runtime that path almost never
 * lines up, so the DAC (and the captured palette) saw ~2 of the slider's
 * updates. Read the ramp D3D accepted directly instead.
 *
 * Miniport layout used (offsets from SetGammaRamp at 0x2C1BD0):
 *   +0x240C           index (0/1) of the current ramp buffer
 *   +0x1C28+0x1DC     ramp buffers, 0x300 bytes each: R[256], G[256], B[256]
 */
#define SCGHOST_MINIPORT_PTR_VA   0x2D2148u
#define MINIPORT_GAMMA_CUR_IDX    0x240Cu
#define MINIPORT_GAMMA_RAMPS      (0x1C28u + 0x1DCu)
#define GAMMA_RAMP_BYTES          0x300u

extern void xbox_GammaSetSourceHook(int (*hook)(uint8_t *out));
extern void scghost_shadows_tick(void);

static int scghost_gamma_source(uint8_t *out)
{
    /* Per-frame tick. The gamma source hook is the only wrapper callback the
     * runtime invokes once per presented frame on both the GDI and the external
     * (D3D11) present paths, so the title's shadow settings (which it reloads
     * from its own config early in startup) are re-asserted here rather than
     * only once. See src/recomp_shadows.c. */
    scghost_shadows_tick();

    uint32_t mp = MEM32(SCGHOST_MINIPORT_PTR_VA);
    uint32_t idx, base;
    int i;

    if (mp == 0 || mp >= 0x08000000u)
        return 0;
    idx = MEM32(mp + MINIPORT_GAMMA_CUR_IDX);
    if (idx > 1)
        return 0;
    base = mp + MINIPORT_GAMMA_RAMPS + idx * GAMMA_RAMP_BYTES;
    /* Before D3D's first SetGammaRamp the buffer is zero; not a real ramp. */
    if (MEM8(base + 255) == 0 && MEM8(base + 256 + 255) == 0 &&
        MEM8(base + 512 + 255) == 0)
        return 0;
    for (i = 0; i < 256; i++) {
        out[i * 3 + 0] = MEM8(base + i);
        out[i * 3 + 1] = MEM8(base + 256 + i);
        out[i * 3 + 2] = MEM8(base + 512 + i);
    }
    return 1;
}

void scghost_video_install(void)
{
    xbox_VideoSetQueryHook(scghost_video_query);
    xbox_VideoSetAvPackHook(scghost_avpack);
    xbox_GammaSetSourceHook(scghost_gamma_source);
}

/* Rewrite the title's 1920x1080 display-mode row so it carries the progressive
 * AV word. The row is keyed by its av_info word; several 1080 rows exist (one
 * per standard byte), matching on resolution keeps them all in sync. Safe to
 * run before the game's D3D has touched the table. */
void scghost_patch_mode_table(void)
{
    static int done = 0;
    uint32_t off;

    if (done)
        return;
    done = 1;

    for (off = DISPLAYMODE_TABLE_VA;
         off + DISPLAYMODE_ROW_BYTES <= DISPLAYMODE_TABLE_VA + DISPLAYMODE_TABLE_LEN;
         off += DISPLAYMODE_ROW_BYTES) {
        uint32_t av = MEM32(off);
        uint32_t wh = MEM32(off + 4);

        if ((wh & 0xFFFFu) != 1920u || (wh >> 16) != 1080u)
            continue;
        if ((av & 0x00FFFFFFu) == (AVWORD_1920x1080 & 0x00FFFFFFu))
            continue;
        MEM32(off) = (av & 0xFF000000u) | (AVWORD_1920x1080 & 0x00FFFFFFu);
        fprintf(stderr, "  [VIDEO] patched 1080 row @%08X av_info %08X -> %08X\n",
                (unsigned)off, (unsigned)av, (unsigned)MEM32(off));
    }
    fflush(stderr);
}
