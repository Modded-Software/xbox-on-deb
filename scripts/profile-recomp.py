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
import os
import re
import subprocess
import sys

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
        except OSError:
            continue
        if "ghost.exe" in cmd and "pw-record" not in cmd:
            pids.append(int(entry))
    return pids


def leaf_samples(perf_data):
    """([IP], tid_counter) from the first frame of every sample."""
    result = subprocess.run(["perf", "script", "-i", perf_data],
                            capture_output=True, text=True)
    ips = []
    expect = False
    for line in result.stdout.splitlines():
        if "cpu-clock" in line and ":" in line:
            expect = True
            continue
        if expect:
            match = _LEAF_RE.match(line)
            if match:
                ips.append(int(match.group(1), 16))
                expect = False
    return ips


def anon_exec_regions(perf_data):
    """[(start, end)] for anonymous executable mappings in the perf stream."""
    result = subprocess.run(["perf", "script", "-D", "-i", perf_data],
                            capture_output=True, text=True)
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


def symbolize(perf_data, exe, report_path=None, top=50):
    """Resolve the profile to lifted functions; returns (base, counts, files)."""
    ips = leaf_samples(perf_data)
    if not ips:
        raise RuntimeError(f"no cpu-clock samples in {perf_data}")
    regions = anon_exec_regions(perf_data)
    region = choose_base(ips, regions)
    if region is None:
        raise RuntimeError("no anonymous executable mapping holds the samples")
    base, end = region
    total = len(ips)

    hist = collections.Counter()
    for ip in ips:
        hist[ip] += 1

    in_pe = sorted(ip for ip in hist if base <= ip < end)
    inp = "".join("0x%x\n" % (PE_IMAGE_BASE + (ip - base)) for ip in in_pe)
    proc = subprocess.run(["llvm-symbolizer", "--output-style=JSON", "--obj=" + exe],
                          input=inp, capture_output=True, text=True)
    funcs = collections.Counter()
    files = collections.Counter()
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        ip = base + (int(obj["Address"], 16) - PE_IMAGE_BASE)
        n = hist.get(ip, 0)
        symbol = obj.get("Symbol") or []
        if symbol:
            frame = symbol[0]
            funcs[frame.get("FunctionName") or "?"] += n
            files[frame.get("FileName") or "?"] += n
        else:
            funcs["?"] += n
            files["?"] += n

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
    report = "\n".join(lines) + "\n"
    if report_path:
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w") as handle:
            handle.write(report)
    return base, funcs, report


ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def record(perf_data, secs=30.0, settle=5.0, user_state=True):
    """Drive the game to the first mission (canonical A-mash) and perf-record it.

    Returns True if a non-empty perf.data was written.
    """
    sys.path.insert(0, os.path.join(ROOT, "recomp", "tests"))
    import framework  # noqa: E402
    game = framework.Game(user_state=user_state)
    print("launching game...", flush=True)
    game.start()
    try:
        print("a-mash until the mission map loads...", flush=True)
        if not game.goto_gameplay(settle=settle):
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