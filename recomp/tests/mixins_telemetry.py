"""Runtime telemetry readers for the recomp test suite: input, GPU, liveness."""
import hashlib
import os
import re
import time

try:
    from . import tconfig
    from .procutil import _run
    from .tconfig import CAPTURE, WINDOW_TITLE, log
except ImportError:
    import tconfig
    from procutil import _run
    from tconfig import CAPTURE, WINDOW_TITLE, log

# The live runtime log path. Read `tconfig.LOG` at call time, not bound here at
# import: the user-state launcher repoints tconfig.LOG to its own timestamped
# log (mixins_lifecycle._start_user_state), and a statically imported copy would
# keep reading the stale recomp_boot.log.


def _log_path():
    return tconfig.LOG


class TelemetryMixin:
    # -- telemetry: mouse / right stick -----------------------------------

    def mouse_move(self, dx, dy, timeout=4.0):
        """Inject relative mouse motion and wait for the input layer to report
        the synthesised right-stick value. None if nothing arrived."""
        offset = os.path.getsize(_log_path()) if os.path.exists(_log_path()) else 0
        self.move(dx, dy)
        deadline = time.time() + timeout
        while time.time() < deadline:
            offset, text = self._read_from(offset)
            for line in text.splitlines():
                found = re.search(
                    r"\[KBM\] mouse dx=(-?\d+) dy=(-?\d+) rx=(-?\d+) ry=(-?\d+)", line)
                if found:
                    return dict(zip(("dx", "dy", "rx", "ry"),
                                    (int(v) for v in found.groups())))
            time.sleep(0.05)
        return None

    def mouse_trace(self):
        with open(_log_path(), "r", errors="replace") as handle:
            return [l for l in handle if "[KBM] mouse" in l]

    def log_offset(self):
        return os.path.getsize(_log_path()) if os.path.exists(_log_path()) else 0

    def log_since(self, offset, tag):
        """Lines containing `tag` appended to the boot log since `offset`."""
        _, text = self._read_from(offset)
        return [l for l in text.splitlines() if tag in l]

    def wait_log_line(self, tag, timeout=25.0, offset=None):
        """Wait for the next boot-log line containing `tag`; None on timeout."""
        if offset is None:
            offset = self.log_offset()
        deadline = time.time() + timeout
        while time.time() < deadline:
            lines = self.log_since(offset, tag)
            if lines:
                return lines[-1]
            time.sleep(0.5)
        return None

    # -- telemetry: GPU health --------------------------------------------

    def shader_failures(self):
        """Vertex+pixel D3DCompile failures from the latest GPU summary."""
        line = self._last_line("[GPU-D3D11] shaders:")
        if line is None:
            return None
        return sum(int(n) for n in re.findall(r"(\d+) failures", line))

    def texture_failures(self):
        """Texture decode+create failures from the latest GPU summary."""
        line = self._last_line("[GPU-D3D11] texture uploads:")
        if line is None:
            return None
        return sum(int(n) for n in re.findall(r"(\d+) (?:decode|create) failures", line))

    def cpu_fallback_batches(self):
        line = self._last_line("[GPU-D3D11] batches:")
        if line is None:
            return None
        match = re.search(r"(\d+) CPU fallback", line)
        return int(match.group(1)) if match else None

    def _last_line(self, tag):
        if not os.path.exists(_log_path()):
            return None
        last = None
        with open(_log_path(), "r", errors="replace") as handle:
            for line in handle:
                if tag in line:
                    last = line
        return last

    # -- telemetry: input state -------------------------------------------

    def _read_from(self, offset):
        if not os.path.exists(_log_path()):
            return offset, ""
        with open(_log_path(), "r", errors="replace") as handle:
            handle.seek(offset)
            text = handle.read()
            return handle.tell(), text

    def latest_input(self):
        with open(_log_path(), "r", errors="replace") as handle:
            last = None
            for line in handle:
                if "[INPUT]" in line:
                    last = line
        if last is None:
            raise RuntimeError("no [INPUT] line in the boot log yet")
        return self._parse_input(last)

    def wait_input(self, timeout=6.0):
        """Wait for the next fresh [INPUT] sample and return it as a dict."""
        deadline = time.time() + timeout
        offset = os.path.getsize(_log_path()) if os.path.exists(_log_path()) else 0
        while time.time() < deadline:
            offset, text = self._read_from(offset)
            for line in text.splitlines():
                if "[INPUT]" in line:
                    return self._parse_input(line)
            time.sleep(0.1)
        raise TimeoutError("no new [INPUT] sample arrived")

    @staticmethod
    def _parse_input(line):
        sample = {}
        for key, value in re.findall(r"(\w+)=(\S+)", line):
            try:
                sample[key] = int(value, 0)
            except ValueError:
                sample[key] = value
        return sample

    def key_trace(self):
        """Recently arriving keys, from the window's own edge log."""
        with open(_log_path(), "r", errors="replace") as handle:
            return [l for l in handle if "[KEY]" in l]

    # -- telemetry: liveness / pixels -------------------------------------

    def title(self):
        return _run("title", WINDOW_TITLE)

    def frame(self):
        match = re.search(r"Frame (\d+)", self.title())
        return int(match.group(1)) if match else -1

    def fps(self):
        match = re.search(r"([\d.]+) FPS", self.title())
        return float(match.group(1)) if match else -1.0

    def measure_fps(self, seconds=6.0, interval=0.5):
        """Sample the window-caption FPS for `seconds`.

        Returns {"min","max","mean","n"} over every valid sample, or None if
        the caption never reported a framerate (e.g. the game is not rendering).
        """
        samples = []
        deadline = time.time() + seconds
        while time.time() < deadline:
            value = self.fps()
            if value >= 0:
                samples.append(value)
            time.sleep(interval)
        if not samples:
            return None
        return {"min": min(samples), "max": max(samples),
                "mean": sum(samples) / len(samples), "n": len(samples)}

    def wait_frame_advance(self, timeout=10.0):
        start = self.frame()
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.frame() > start:
                return True
            time.sleep(0.2)
        return False

    def capture_hash(self, timeout=5.0):
        """Trigger a framebuffer dump (F12) and hash it; None if it never came."""
        try:
            os.remove(CAPTURE)
        except FileNotFoundError as exc:
            log.info("no previous capture at %s to remove: %s", CAPTURE, exc)
        self.focus()
        self.key("F12", "press")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if os.path.exists(CAPTURE) and os.path.getsize(CAPTURE) > 0:
                time.sleep(0.1)  # let the write finish
                with open(CAPTURE, "rb") as handle:
                    return hashlib.sha256(handle.read()).hexdigest()[:16]
            time.sleep(0.1)
        return None