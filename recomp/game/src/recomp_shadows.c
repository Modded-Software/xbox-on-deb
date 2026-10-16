/**
 * StarCraft: Ghost runtime control of the title's own dynamic shadows.
 *
 * The title keeps its shadow settings in the global render-options object at
 * guest VA 0x49E630 (the same object recomp_video.c rewrites for resolution).
 * The shadow fields are:
 *
 *   +0x14  0x49E644  int    shadow type:
 *                              0 = Off            1 = Drop
 *                              2 = Rough texture  3 = Full texture
 *                              4 = Full texture (HW)   5 = Full poly
 *   +0x18  0x49E648  float  shadow-model detail / LOD (cModel_GetShadow,
 *                           0x1F20C0, passes it to cModelInst::SetDetail)
 *   +0x1C  0x49E64C  float  shadow detail parameter 2
 *   +0x20  0x49E650  float  shadow detail parameter 3
 *   +0x24  0x49E654  float  shadow detail parameter 4
 *   +0x28  0x49E658  int    max object shadows per object (clamped to 10)
 *
 * These are exactly the cells the title's console commands write
 * (c:/star/code/game/ui/vuiconsole.cpp):
 *
 *   shadow <type> <f0> <f1> <f2> <f3>   CmdShadow   (0x22730)
 *   toggleshadows                       CmdToggleShadows (0x22900)  0 <-> 3
 *   numshadows <n>                      CmdNumShadows (0x23340)
 *
 * In this build the type is only ever compared against zero
 * (tThing_FindIdealShadowLight 0x38CC0 and tThing_DrawShadow 0x38DA0 both bail
 * on 0), so it behaves as an on/off switch: a zero type -- or a zero count --
 * removes every dynamic shadow the title draws. That is the useful case here:
 * turn the title's hardware shadow maps off so a screen-space / path-traced
 * effect (e.g. iMMERSE RELIGHT's shadow tracing) can supply them instead,
 * without the two fighting. Values 1..5 are accepted for completeness (they
 * select a labelled type in the console) but render identically.
 *
 * The title reloads these from its own command-line/config parser early in
 * startup, so the values are re-asserted every presented frame from
 * scghost_shadows_tick() (driven by the video module's per-frame hook) rather
 * than only once at install.
 *
 * Environment:
 *   SCGHOST_SHADOWS        off | on | 0..5      shadow type (off == disabled)
 *   SCGHOST_SHADOW_COUNT   0..10                max object shadows per object
 *   SCGHOST_SHADOW_DETAIL  f0 [f1 [f2 [f3]]]    shadow detail floats
 *
 * Anything unset is left at whatever the title chose.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include "recomp_types.h"

#define SCGHOST_SHADOW_TYPE_VA   0x49E644u
#define SCGHOST_SHADOW_DETAIL_VA 0x49E648u
#define SCGHOST_SHADOW_COUNT_VA  0x49E658u

static int      s_set_type;
static uint32_t s_type;
static int      s_set_count;
static uint32_t s_count;
static int      s_set_detail;
static float    s_detail[4];

static int parse_long(const char *s, long *out)
{
    char *end;
    long v;

    if (!s || !*s)
        return 0;
    v = strtol(s, &end, 0);
    if (end == s || *end)
        return 0;
    *out = v;
    return 1;
}

static int parse_float(const char *s, float *out)
{
    char *end;
    float v;

    if (!s || !*s)
        return 0;
    v = strtof(s, &end);
    if (end == s || *end)
        return 0;
    *out = v;
    return 1;
}

static void parse_type(const char *v)
{
    long n;

    if (!v || !*v)
        return;
    if (!strcmp(v, "off") || !strcmp(v, "none") || !strcmp(v, "no"))
        s_type = 0;
    else if (!strcmp(v, "on") || !strcmp(v, "full") || !strcmp(v, "default"))
        s_type = 3;   /* the title's own "shadows on" type (CmdToggleShadows) */
    else if (parse_long(v, &n) && n >= 0 && n <= 5)
        s_type = (uint32_t)n;
    else {
        fprintf(stderr, "  [SHADOWS] ignoring SCGHOST_SHADOWS='%s' "
                        "(want off|on|0..5)\n", v);
        return;
    }
    s_set_type = 1;
}

/* Re-assert the requested settings. Cheap; called once per presented frame. */
void scghost_shadows_tick(void)
{
    if (s_set_type)
        MEM32(SCGHOST_SHADOW_TYPE_VA) = s_type;
    if (s_set_count)
        MEM32(SCGHOST_SHADOW_COUNT_VA) = s_count;
    if (s_set_detail) {
        MEMF(SCGHOST_SHADOW_DETAIL_VA + 0) = s_detail[0];
        MEMF(SCGHOST_SHADOW_DETAIL_VA + 4) = s_detail[1];
        MEMF(SCGHOST_SHADOW_DETAIL_VA + 8) = s_detail[2];
        MEMF(SCGHOST_SHADOW_DETAIL_VA + 12) = s_detail[3];
    }
}

/* Shadow-map texture size (square, pixels). The title creates its shadow
 * buffer as a 256x256 cTexture in worldEffects_Startup (0x36460,
 * `cTexture::NewBlank(256, 256, 7, 0x100, "ShadowBuffer", 0)`). That call site
 * is hand-patched in the generated code to push this function for width and
 * height; the render camera derives its canvas from the texture's own
 * dimensions (tRenderCamera::SetRenderTarget, 0x1EFD30 reads +0x34/+0x36), so
 * scaling here scales the shadow map with no other change.
 *
 * SCGHOST_SHADOW_TEX          explicit size, e.g. 1024 (4x the pixels)
 * SCGHOST_SHADOW_TEX_SCALE    multiplier on the 512 default, e.g. 2 -> 1024
 * Default 512 (2x the title's own 256). Clamped to [64, 2048]. */
uint32_t scghost_shadow_tex_size(void)
{
    static int inited;
    static uint32_t size = 512;

    if (!inited) {
        const char *v;
        long n;

        inited = 1;
        v = getenv("SCGHOST_SHADOW_TEX");
        if (v && *v && parse_long(v, &n) && n > 0) {
            size = (uint32_t)n;
        } else {
            v = getenv("SCGHOST_SHADOW_TEX_SCALE");
            if (v && *v && parse_long(v, &n) && n > 0)
                size = 512u * (uint32_t)n;
        }
        if (size < 64)
            size = 64;
        if (size > 2048)
            size = 2048;
        fprintf(stderr, "  [SHADOWS] shadow map texture = %ux%u\n", size, size);
    }
    return size;
}

void scghost_shadows_install(void)
{
    const char *v;
    long n;

    parse_type(getenv("SCGHOST_SHADOWS"));

    v = getenv("SCGHOST_SHADOW_COUNT");
    if (v && *v) {
        if (parse_long(v, &n)) {
            if (n < 0)
                n = 0;
            if (n > 10) {
                fprintf(stderr, "  [SHADOWS] SCGHOST_SHADOW_COUNT=%ld clamped to 10\n", n);
                n = 10;
            }
            s_count = (uint32_t)n;
            s_set_count = 1;
        } else {
            fprintf(stderr, "  [SHADOWS] ignoring SCGHOST_SHADOW_COUNT='%s' (want 0..10)\n", v);
        }
    }

    v = getenv("SCGHOST_SHADOW_DETAIL");
    if (v && *v) {
        char buf[128];
        char *tok, *save = NULL;
        int i = 0;

        strncpy(buf, v, sizeof(buf) - 1);
        buf[sizeof(buf) - 1] = '\0';
        for (tok = strtok_r(buf, " ,", &save); tok && i < 4;
             tok = strtok_r(NULL, " ,", &save)) {
            if (!parse_float(tok, &s_detail[i])) {
                fprintf(stderr, "  [SHADOWS] ignoring SCGHOST_SHADOW_DETAIL='%s' (bad float '%s')\n",
                        v, tok);
                i = 0;
                break;
            }
            i++;
        }
        if (i > 0)
            s_set_detail = 1;
    }

    scghost_shadows_tick();

    if (s_set_type)
        fprintf(stderr, "  [SHADOWS] shadow type = %u (%s)\n", s_type,
                s_type == 0 ? "off" : "on");
    if (s_set_count)
        fprintf(stderr, "  [SHADOWS] max object shadows = %u\n", s_count);
    if (s_set_detail)
        fprintf(stderr, "  [SHADOWS] shadow detail = %.2f %.2f %.2f %.2f\n",
                s_detail[0], s_detail[1], s_detail[2], s_detail[3]);
    if (!s_set_type && !s_set_count && !s_set_detail)
        fprintf(stderr, "  [SHADOWS] no override set; title defaults in use\n");
}