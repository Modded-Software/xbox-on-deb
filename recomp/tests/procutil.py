"""Process helpers for the recomp test suite: run xinject, find/kill ghost.exe."""
import os
import signal
import subprocess
import sys
import time

try:
    from .tconfig import XINJECT, log
except ImportError:
    from tconfig import XINJECT, log


def _run(*args, check=True):
    result = subprocess.run([sys.executable, XINJECT, *args],
                            capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"xinject {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _ghost_pids():
    """PIDs of any running ghost.exe, found via /proc (Proton detaches it
    from the launched session, so killing the process group is not enough).

    Match the binary path, not the bare name: a shell command that merely
    mentions "ghost.exe" (say, the one running these tests) must not be
    mistaken for the game."""
    me = os.getpid()
    pids = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit() or int(entry) == me:
            continue
        try:
            with open(f"/proc/{entry}/cmdline", "rb") as handle:
                cmdline = handle.read().replace(b"\x00", b" ").decode("utf-8", "replace")
        except OSError as exc:
            log.info("read /proc/%s/cmdline failed: %s", entry, exc)
            continue
        if "/ghost.exe" in cmdline or "\\ghost.exe" in cmdline:
            pids.append(int(entry))
    return pids


def kill_ghost():
    """Terminate every running ghost.exe, then force-kill any survivor."""
    pids = _ghost_pids()
    if not pids:
        return 0
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError as exc:
            log.info("ghost pid %s already exited before SIGTERM: %s", pid, exc)
    deadline = time.time() + 10
    while time.time() < deadline and _ghost_pids():
        time.sleep(0.2)
    for pid in _ghost_pids():
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError as exc:
            log.info("ghost pid %s already exited before SIGKILL: %s", pid, exc)
    return len(pids)