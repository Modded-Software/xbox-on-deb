"""Mission navigation and app-audio capture for the recomp test suite."""
import subprocess
import time

try:
    from .audio import Recorder, _ghost_audio_nodes, _stream_volume
    from .tconfig import log
except ImportError:
    from audio import Recorder, _ghost_audio_nodes, _stream_volume
    from tconfig import log


class NavMixin:
    MISSION_MAP = "1_3_1b_Hive_StationOuter"

    # World-geometry vertex shaders: first loaded when the level itself is
    # drawn (after the "press A" loading screen), never by the menu.
    WORLD_SHADER = "\\VertexShaders\\xbox\\DefaultWorld"

    def goto_mission(self, key="space", gap=2.0, timeout=240.0):
        """Mash A every `gap` seconds until the first mission's map loads.

        Arrival is detected from the runtime log: the level manager logs the
        map it streams in ([PATH] ...\\Levels\\1_3_1b_Hive_StationOuter.nhc).
        Returns the map name, or None on timeout. `key` is Space (A) unless
        overridden.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            # The game window loses keyboard focus after the logo videos, so
            # a one-shot focus() at launch is not enough: without re-focusing
            # each tap, every press goes to whatever window stole focus and
            # the title idles into attract mode.
            self.focus()
            self.tap(key, hold=0.35, gap=0.0)
            time.sleep(max(0.0, gap - 0.35))
            # Only the level file itself: the bare map name first appears in
            # the asset manifest (<map>.reslog) and .nnb/.xpr/.nmb loads,
            # which all stream in while the menu cutscene is still running.
            if self._last_line(f"\\Levels\\{self.MISSION_MAP}.nhc"):
                return self.MISSION_MAP
        return None

    def wait_quiet(self, tag="[PATH]", quiet=5.0, timeout=120.0, key=None, gap=2.0):
        """Wait until no new `tag` log line appeared for `quiet` seconds while
        frames kept advancing. With `key`, tap it every `gap` s meanwhile (to
        get past press-A screens). False on timeout."""
        offset = self.log_offset()
        calm, frame = time.time(), self.frame()
        deadline = time.time() + timeout
        while time.time() < deadline:
            if key:
                self.focus()
                self.tap(key, hold=0.35, gap=max(0.0, gap - 0.35))
            else:
                time.sleep(0.5)
            offset, text = self._read_from(offset)
            if tag in text:
                calm, frame = time.time(), self.frame()
            elif time.time() - calm >= quiet and self.frame() > frame:
                return True
        return False

    def goto_gameplay(self, key="space", gap=2.0, timeout=240.0, quiet=5.0):
        """Reach the first mission and keep going until it is actually playable.

        `goto_mission` stops at the level .nhc, which only *starts* the load.
        After it the game sits on a "press A" loading screen, then a comms
        briefing (shuttleescape.NCS + 02_131b.bik) that also waits for A. Keep
        tapping A until the world shaders have loaded and [PATH] streaming
        has been quiet for `quiet` s with frames advancing.
        """
        if self.goto_mission(key=key, gap=gap, timeout=timeout) != self.MISSION_MAP:
            return False
        deadline = time.time() + timeout
        while not self._last_line(self.WORLD_SHADER):
            if time.time() > deadline:
                return False
            self.focus()
            self.tap(key, hold=0.35, gap=max(0.0, gap - 0.35))
        return self.wait_quiet(quiet=quiet, timeout=timeout, key=key, gap=gap)

    def start_app_recording(self, path):
        """Record only ghost.exe's own PipeWire output to `path` (s16 WAV).

        This is the audible signal -- what the sound server actually plays --
        not the runtime's internal PCM. Returns a Recorder; call stop().
        Raises if ghost.exe has no playback stream at all."""
        nodes = _ghost_audio_nodes()
        if not nodes:
            raise RuntimeError(
                "ghost.exe has no PipeWire Stream/Output/Audio node: its audio "
                "is not reaching the sound server")
        node_id, props = nodes[0]
        target = props.get("node.name") or str(props.get("object.serial", node_id))
        # The desktop may remember a low/muted per-app volume (WirePlumber's
        # restore-stream), which is not the game's doing. Normalise it for the
        # measurement and put it back afterwards, so the test measures whether
        # the game emits audio, not how the mixer was left.
        restore = _stream_volume(node_id)
        subprocess.run(["wpctl", "set-mute", str(node_id), "0"])
        subprocess.run(["wpctl", "set-volume", str(node_id), "1.0"])
        proc = subprocess.Popen(
            ["pw-record", "--target", target, "--rate", "48000",
             "--channels", "2", "--format", "s16", path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
        return Recorder(proc, path, node_id=node_id, restore=restore)