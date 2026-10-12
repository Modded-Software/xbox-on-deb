"""PipeWire audio capture helpers for the recomp test suite.

Split out of framework.py; used by Game.start_app_recording.
"""
import json
import re
import subprocess

try:
    from .procutil import _ghost_pids
    from .tconfig import log
except ImportError:
    from procutil import _ghost_pids
    from tconfig import log


def _pw_nodes():
    """(id, props) for every PipeWire node, from pw-dump. Empty on failure."""
    result = subprocess.run(["pw-dump"], capture_output=True, text=True)
    if result.returncode != 0:
        log.warning("pw-dump failed: %s", result.stderr.strip())
        return []
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        log.warning("pw-dump output was not JSON: %s", exc)
        return []
    nodes = []
    for obj in data:
        if obj.get("type") != "PipeWire:Interface:Node":
            continue
        props = obj.get("info", {}).get("props") or {}
        nodes.append((obj.get("id"), props))
    return nodes


def _ghost_audio_nodes():
    """PipeWire playback streams that belong to ghost.exe.

    Matched by process id first (Proton keeps the wine process whose cmdline
    contains the exe path), then by an application/binary/name that mentions
    ghost, wine or FAudio, since the Wine audio backend's ids vary."""
    pids = set(_ghost_pids())
    wanted = ("ghost", "wine", "faudio")
    found = []
    for node_id, props in _pw_nodes():
        if props.get("media.class") != "Stream/Output/Audio":
            continue
        blob = " ".join(str(props.get(k, "")) for k in (
            "application.name", "application.process.binary",
            "node.name", "media.name")).lower()
        if props.get("application.process.id") in pids or any(w in blob for w in wanted):
            found.append((node_id, props))
    return found


class Recorder:
    """A running pw-record capture; stop() finalises the WAV and returns it."""

    def __init__(self, proc, path, node_id=None, restore=None):
        self.proc = proc
        self.path = path
        self.node_id = node_id
        self.restore = restore

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        if self.node_id is not None and self.restore is not None:
            mute = subprocess.run(["wpctl", "set-mute", str(self.node_id),
                                   "1" if self.restore[0] else "0"],
                                  capture_output=True, text=True)
            if mute.returncode != 0:
                log.warning("wpctl set-mute %s failed: %s",
                            self.node_id, mute.stderr.strip())
            vol = subprocess.run(["wpctl", "set-volume", str(self.node_id),
                                  f"{self.restore[1]:.4f}"],
                                 capture_output=True, text=True)
            if vol.returncode != 0:
                log.warning("wpctl set-volume %s failed: %s",
                            self.node_id, vol.stderr.strip())
        return self.path


def _stream_volume(node_id):
    """(muted, volume) for a PipeWire node, via wpctl. (False, 1.0) if unknown."""
    try:
        proc = subprocess.run(["wpctl", "get-volume", str(node_id)],
                              capture_output=True, text=True)
    except OSError as exc:
        log.warning("wpctl get-volume %s failed: %s", node_id, exc)
        return False, 1.0
    if proc.returncode != 0:
        log.warning("wpctl get-volume %s failed: %s", node_id, proc.stderr.strip())
        return False, 1.0
    out = proc.stdout
    muted = "MUTED" in out
    volume = 1.0
    match = re.search(r"Volume:\s*([0-9.]+)", out)
    if match:
        volume = float(match.group(1))
    return muted, volume