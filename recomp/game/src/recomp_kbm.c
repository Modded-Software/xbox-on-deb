/**
 * StarCraft: Ghost - KBM direct look: switch off the title's own camera
 * correctors.
 *
 * With RECOMP_KBM=1 and direct look on (the default), the mouse delta is added
 * straight to the local camera's yaw/pitch once per pad poll
 * (refs/xboxrecomp/src/input/xinput_device.c, kbm_state). The title then runs
 * two correctors of its own every tick, and both only exist for stick play:
 *
 *   tSimCamera::UpdateYaw  (0x57560) - while moving it calls
 *     tSimCamera::ShouldAutoYaw (0x55740) and, when that says yes, turns the
 *     camera toward the movement heading (velocity at +0xB4 -> ArcTan4) with a
 *     rate-limited LerpAngle, `*0x491CB0 * *0x361FC8` degrees per tick.
 *   tSimCamera::UpdatePitch (0x55450) - while moving it recenters +0x114
 *     toward (+0x124 + +0x104).
 *
 * Between two polls those pull the view back toward where the stick would have
 * left it, so the look advances and is dragged back once per tick: a visible
 * stutter that appears the moment the player moves (A/D strafing included) and
 * vanishes when standing still. The generated ShouldAutoYaw is patched to
 * return 0 while this returns 1, which leaves the mouse as the only author of
 * the camera.
 *
 * RECOMP_KBM_NO_AUTOYAW=0 restores the title's behaviour for A/B testing.
 */
#include <stdlib.h>

int scghost_kbm_no_autoyaw(void)
{
    static int cached = -1;

    if (cached < 0) {
        const char *kbm = getenv("RECOMP_KBM");
        const char *direct = getenv("RECOMP_KBM_LOOK_DIRECT");
        const char *off = getenv("RECOMP_KBM_NO_AUTOYAW");
        int kbm_on = kbm && *kbm && *kbm != '0';
        int direct_on = !(direct && *direct == '0');
        int wanted = !(off && *off == '0');
        cached = (kbm_on && direct_on && wanted) ? 1 : 0;
    }
    return cached;
}
