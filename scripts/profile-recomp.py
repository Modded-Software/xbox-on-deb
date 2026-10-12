#!/usr/bin/env python3
"""Symbolicate a perf profile of the recompiled game.

Wine maps the ghost.exe PE anonymously, so perf labels its samples ``[JIT]``
and cannot name them. This turns a perf.data into function-level attribution by:

  1. parsing the leaf IP of every sample from ``perf script``;
  2. finding which anonymous executable mapping (a ``PERF_RECORD_MMAP2``) those
     IPs fall in -- that mapping is the PE, loaded somewhere ASLR chose;
  3. converting each IP to a PE RVA (IP - load_base + ImageBase) and resolving
     it with ``llvm-symbolizer`` against ghost.exe/ghost.pdb;
  4. writing a report grouped by lifted function and by source file.

Importable (call ``symbolize``) or run directly on an existing perf.data:

    scripts/profile-recomp.py --symbolize-only --perf /tmp/opencode/perf.data
"""
import collections
import json
import logging
import os
import re
import subprocess
import sys

log = logging.getLogger("profile-recomp")

PE_IMAGE_BASE = 0x140000000
_LEAF_RE = re.compile(r"^\s+([0-9a-f]+)\b")
_HDR_RE = re.compile(r"^\S+\s+(\d+)\s+[\d.]+:.*cpu-clock")
_MAP2_RE = re.compile(
    r"PERF_RECORD_MMAP2.*?: \[(0x[0-9a-f]+)\((0x[0-9a-f]+)\).*?\]: (\S+) (\S+)")


def find_ghost_pids():
    """PIDs whose cmdline names ghost.exe (excludes pw-record helpers)."""
    pids = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/cmdline", "rb") as handle:
                cmd = handle.read().replace(b"\x00", b" ").decode("utf-8", "replace")
        except OSError as exc:
            log.info("read /proc/%s/cmdline failed: %s", entry, exc)
            continue
        if "ghost.exe" in cmd and "pw-record" not in cmd:
            pids.append(int(entry))
    return pids


def stack_samples(perf_data):
    """[(tid, [IP, ...leaf first])] for every sample."""
    result = subprocess.run(["perf", "script", "-i", perf_data],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"perf script failed (rc={result.returncode}): {result.stderr.strip()}")
    samples = []
    for line in result.stdout.splitlines():
        hdr = _HDR_RE.match(line)
        if hdr:
            samples.append((int(hdr.group(1)), []))
            continue
        match = _LEAF_RE.match(line)
        if match and samples:
            samples[-1][1].append(int(match.group(1), 16))
    return [s for s in samples if s[1]]


def anon_exec_regions(perf_data):
    """[(start, end)] for anonymous executable mappings in the perf stream."""
    result = subprocess.run(["perf", "script", "-D", "-i", perf_data],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"perf script -D failed (rc={result.returncode}): {result.stderr.strip()}")
    regions = []
    for line in result.stdout.splitlines():
        match = _MAP2_RE.search(line)
        if not match or "//anon" not in line:
            continue
        start = int(match.group(1), 16)
        size = int(match.group(2), 16)
        perms = match.group(3)
        if "x" in perms:
            regions.append((start, start + size))
    return regions


def choose_base(ips, regions):
    """The anon exec region holding the most sample IPs is the PE image."""
    best, best_hits = None, 0
    for start, end in regions:
        hits = sum(1 for ip in ips if start <= ip < end)
        if hits > best_hits:
            best, best_hits = (start, end), hits
    return best


def section_base(exe, region_size):
    """VMA the anonymous mapping ``region_size`` bytes long starts at.

    Wine maps the PE's executable section anonymously, and the mapping begins
    at that section's VMA -- ImageBase + SectionAlignment, not ImageBase. Taking
    the mapping start for ImageBase shifted every symbol by 0x1000, which made
    init code (xbox_MemoryLayoutInit, xbox_AllocThreadTib) look hot and hid the
    real offender. Anchor on the exec section whose page-rounded size matches
    the mapping, using ImageBase when nothing matches.
    """
    try:
        proc = subprocess.run(["llvm-objdump", "-h", exe],
                              capture_output=True, text=True)
    except OSError as exc:
        log.warning("llvm-objdump -h %s failed: %s", exe, exc)
        return PE_IMAGE_BASE
    if proc.returncode != 0:
        log.warning("llvm-objdump -h %s failed (rc=%d): %s",
                    exe, proc.returncode, proc.stderr.strip())
        return PE_IMAGE_BASE
    out = proc.stdout
    for line in out.splitlines():
        match = re.match(r"\s*\d+\s+(\S+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+(\S+)", line)
        if not match or match.group(4) != "TEXT":
            continue
        size, vma = int(match.group(2), 16), int(match.group(3), 16)
        if (size + 0xFFF) & ~0xFFF == region_size:
            return vma
    return PE_IMAGE_BASE


def symbolize(perf_data, exe, report_path=None, top=50):
    """Resolve the profile to lifted functions; returns (base, counts, files)."""
    samples = stack_samples(perf_data)
    ips = [stack[0] for _, stack in samples]
    if not ips:
        raise RuntimeError(f"no cpu-clock samples in {perf_data}")
    regions = anon_exec_regions(perf_data)
    region = choose_base(ips, regions)
    if region is None:
        raise RuntimeError("no anonymous executable mapping holds the samples")
    base, end = region
    anchor = section_base(exe, end - base)
    total = len(ips)

    hist = collections.Counter(ips)
    every = {ip for _, stack in samples for ip in stack if base <= ip < end}
    inp = "".join("0x%x\n" % (anchor + (ip - base)) for ip in sorted(every))
    proc = subprocess.run(["llvm-symbolizer", "--output-style=JSON", "--obj=" + exe],
                          input=inp, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"llvm-symbolizer failed (rc={proc.returncode}): {proc.stderr.strip()}")
    names = {}  # ip -> (function, file)
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        ip = base + (int(obj["Address"], 16) - anchor)
        symbol = obj.get("Symbol") or []
        frame = symbol[0] if symbol else {}
        names[ip] = (frame.get("FunctionName") or "?", frame.get("FileName") or "?")
    funcs = collections.Counter()
    files = collections.Counter()
    for ip, n in hist.items():
        if ip in names:
            funcs[names[ip][0]] += n
            files[names[ip][1]] += n

    # Per-thread split, and who calls the bulk copy/compare routines. The PE is
    # built without frame pointers, so the "caller" is the first in-PE frame of
    # whatever chain perf recovered; unattributed shown as "?".
    hot = ("memcpy", "copyBlocks", "memcmp", "memset", "memmove")
    tids = collections.Counter()
    tid_top = collections.defaultdict(collections.Counter)
    callers = collections.Counter()
    for tid, stack in samples:
        tids[tid] += 1
        leaf = names.get(stack[0], ("<outside PE>",))[0]
        tid_top[tid][leaf] += 1
        if any(h in leaf for h in hot):
            caller = next((names[ip][0] for ip in stack[1:]
                           if ip in names and not any(h in names[ip][0] for h in hot)), "?")
            callers[f"{leaf} <- {caller}"] += 1

    pe_total = sum(funcs.values())
    lines = []
    lines.append(f"perf data : {perf_data}")
    lines.append(f"PE base   : 0x{base:x}..0x{end:x}  ({pe_total}/{total} samples in PE)")
    lines.append("")
    lines.append(f"=== top {top} lifted functions (self samples) ===")
    for name, n in funcs.most_common(top):
        lines.append(f"  {n:6d}  {100.0 * n / total:5.1f}%  {name}")
    lines.append("")
    lines.append("=== top source files ===")
    for name, n in files.most_common(25):
        lines.append(f"  {n:6d}  {100.0 * n / total:5.1f}%  {name}")
    lines.append("")
    lines.append("=== threads (samples, top 3 leaves) ===")
    for tid, n in tids.most_common(12):
        tops = ", ".join(f"{f} {c}" for f, c in tid_top[tid].most_common(3))
        lines.append(f"  {tid:8d} {n:6d}  {100.0 * n / total:5.1f}%  {tops}")
    lines.append("")
    lines.append("=== bulk copy/compare callers (no frame pointers) ===")
    for name, n in callers.most_common(25):
        lines.append(f"  {n:6d}  {100.0 * n / total:5.1f}%  {name}")
    report = "\n".join(lines) + "\n"
    if report_path:
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w") as handle:
            handle.write(report)
    return base, funcs, report


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import ROOT_DIR

ROOT = str(ROOT_DIR)


def record(perf_data, secs=30.0, settle=5.0, user_state=True):
    """Drive the game to the first mission (canonical A-mash) and perf-record it.

    Returns True if a non-empty perf.data was written.
    """
    sys.path.insert(0, os.path.join(ROOT, "recomp", "tests"))
    import framework
    game = framework.Game(user_state=user_state)
    print("launching game...", flush=True)
    game.start()
    try:
        print("a-mash until the mission map loads...", flush=True)
        if not game.goto_gameplay(quiet=settle):
            raise RuntimeError("never reached the first mission")
        print("mission loaded: frame=%s fps=%s hash=%s"
              % (game.frame(), game.fps(), game.capture_hash()), flush=True)
        pids = find_ghost_pids()
        print("ghost pids:", pids, flush=True)
        if not pids:
            raise RuntimeError("no ghost.exe process found")
        args = ["perf", "record", "-e", "cpu-clock", "-F", "399", "-g",
                "-o", perf_data]
        for pid in pids:
            args += ["-p", str(pid)]
        args += ["--", "sleep", str(secs)]
        print("running:", " ".join(args), flush=True)
        result = subprocess.run(args, capture_output=True, text=True)
        print("perf:", result.stderr.strip(), flush=True)
        return os.path.exists(perf_data) and os.path.getsize(perf_data) > 0
    finally:
        game.stop()


def main(argv):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbolize-only", action="store_true",
                        help="symbolicate --perf and exit (no game launch)")
    parser.add_argument("--perf", default="/tmp/opencode/perf-recomp.data")
    parser.add_argument("--exe", default=os.path.join(
        ROOT, "recomp", "game", "build", "ghost.exe"))
    parser.add_argument("--report", default=None)
    parser.add_argument("--secs", type=float, default=30.0,
                        help="seconds to sample (record mode)")
    parser.add_argument("--settle", type=float, default=5.0,
                        help="seconds to wait after the mission map loads")
    parser.add_argument("--test-env", action="store_true",
                        help="use the test launcher instead of the user launcher")
    args = parser.parse_args(argv)

    exe = os.path.abspath(args.exe)
    report = args.report or os.path.splitext(args.perf)[0] + ".report.txt"
    if not args.symbolize_only:
        if not record(args.perf, secs=args.secs, settle=args.settle,
                      user_state=not args.test_env):
            print("ERROR: perf record produced no data", file=sys.stderr)
            return 1
    base, funcs, text = symbolize(args.perf, exe, report_path=report)
    sys.stdout.write(text)
    print(f"\nreport: {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))