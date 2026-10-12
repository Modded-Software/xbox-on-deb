"""Game lifecycle for the recomp test suite: launch, attach, user-state, stop."""
import os
import signal
import subprocess

try:
    from . import tconfig
    from .procutil import _run, kill_ghost
except ImportError:
    import tconfig
    from procutil import _run, kill_ghost


class LifecycleMixin:
    def start(self):
        try:                       # start each run with no key held
            open(tconfig.INPUT_HOST, "w").close()
        except OSError as exc:
            tconfig.log.warning("could not clear input file %s: %s", tconfig.INPUT_HOST, exc)
        if self.user_state:
            self._start_user_state()
            self.focus()
            return self
        if self.attach:
            if not os.path.exists(tconfig.LOG):
                raise RuntimeError(f"attach requested but {tconfig.LOG} does not exist")
            self._log_pos = os.path.getsize(tconfig.LOG)
            _run("wait", tconfig.WINDOW_TITLE, str(self.boot_timeout))
        else:
            kill_ghost()  # clear any stale instance so runs never stack
            env = dict(os.environ)
            env["GHOST_GAME_DIR"] = tconfig.GAME_DIR
            env["KBM"] = "1" if self.kbm else "0"
            env["DIAG"] = "1"
            env["RECOMP_KEY_TRACE"] = "1"
            env["RECOMP_KBM_TRACE"] = "1"
            env["RECOMP_FB_CAPTURE"] = tconfig.CAPTURE
            env["RECOMP_INPUT_FILE"] = tconfig.INPUT_FILE
            env.setdefault("RECOMP_NO_FOCUS", "1")
            try:
                os.remove(tconfig.LOG)
            except FileNotFoundError as exc:
                tconfig.log.info("no previous log at %s to remove: %s", tconfig.LOG, exc)
            out = open(os.path.join("/tmp/opencode", "test_game.out"), "w")
            try:
                self.proc = subprocess.Popen(
                    ["bash", "scripts/14-launch-recomp.sh"], cwd=tconfig.ROOT, env=env,
                    stdout=out, stderr=subprocess.STDOUT,
                    start_new_session=True)
            finally:
                out.close()  # the child holds its own copy
            _run("wait", tconfig.WINDOW_TITLE, str(self.boot_timeout))
            self._log_pos = 0
        self.focus()
        return self

    def _start_user_state(self):
        """Launch the default user configuration (scripts/18-launch-user.sh).

        This is the same entry point a human uses: it selects keyboard+mouse,
        input/key tracing, the default resolution, the emulated APU, and its
        own timestamped runtime log. It redirects the log to
        logs/latest-runtime.log, which is where this Game then reads telemetry
        from, so tconfig.LOG is repointed for the one live game."""
        env = dict(os.environ)  # ambient env passes through (diagnostic knobs too)
        env["GHOST_GAME_DIR"] = tconfig.GAME_DIR
        env["RECOMP_INPUT_FILE"] = tconfig.INPUT_FILE
        env.setdefault("RECOMP_NO_FOCUS", "1")
        env.setdefault("RECOMP_FB_CAPTURE", tconfig.CAPTURE)  # F12 dump for capture_hash()
        # Capture the decoded/played APU PCM so an audio assertion has a signal
        # to measure. RECOMP_APU_WAV=<path> writes <path>.emu.raw (post-DSP,
        # pre-mixer) and <path>.mix.raw (post-mixer, what is played).
        env.setdefault("RECOMP_APU_WAV", os.path.join("/tmp/opencode", "mission_audio"))
        self.audio_raw = env["RECOMP_APU_WAV"]
        out = open(os.path.join("/tmp/opencode", "test_mission.out"), "w")
        try:
            subprocess.Popen(
                ["bash", "scripts/18-launch-user.sh"], cwd=tconfig.ROOT, env=env,
                stdout=out, stderr=subprocess.STDOUT,
                start_new_session=True)
        finally:
            out.close()
        _run("wait", tconfig.WINDOW_TITLE, str(self.boot_timeout))
        latest = os.path.join(tconfig.ROOT, "logs", "latest-runtime.log")
        tconfig.LOG = os.path.realpath(latest) if os.path.exists(latest) else tconfig.LOG
        self._log_pos = 0
        self.focus()

    def stop(self):
        if self.attach:
            return
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
            except ProcessLookupError as exc:
                tconfig.log.info("game process group already gone before SIGTERM: %s", exc)
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
        self.proc = None
        kill_ghost()

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()