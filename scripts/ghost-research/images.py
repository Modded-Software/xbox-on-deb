#!/usr/bin/env python3
"""Fetch and optimize the curated StarCraft: Ghost imagery.

Reads scripts/ghost-research/image-sources.json, downloads each original from
the Wayback Machine raw endpoint into res/ (gitignored), then writes optimized
WebP and JPEG derivatives into wiki/site/assets/media/ (gitignored) and a
tracked credits file.

Run:  .venv-wiki/bin/python scripts/ghost-research/images.py [--limit N] [--force]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageOps

REPO = Path(__file__).resolve().parents[2]
SOURCES = REPO / "scripts" / "ghost-research" / "image-sources.json"
CDX = REPO / "res" / "starcraft-ghost-archive" / "ghost-images-cdx.txt"
RAW = REPO / "res" / "starcraft-ghost-archive" / "images"
MEDIA = REPO / "wiki" / "site" / "assets" / "media"
CREDITS = REPO / "wiki" / "docs" / "IMAGE-CREDITS.md"

ROLE_WIDTH = {"hero": 1600, "plate": 1024, "thumb": 480}
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
MAGIC = {b"\xff\xd8": "jpg", b"\x89PNG": "png", b"GIF8": "gif", b"RIFF": "webp"}


def load_cdx() -> dict[str, tuple[str, str]]:
    table: dict[str, tuple[str, str]] = {}
    if not CDX.exists():
        return table
    for line in CDX.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        ts, url = parts[0], parts[1]
        norm = url.replace(":80", "").replace("\\", "/")
        path = urlparse(norm).path
        table.setdefault(path, (ts, norm))
    return table


def archive_url(url: str, table: dict[str, tuple[str, str]]) -> str:
    path = urlparse(url).path
    ts = table.get(path, ("2005", url))[0]
    return f"https://web.archive.org/web/{ts}id_/{url}"


def sniff(data: bytes) -> str | None:
    for magic, kind in MAGIC.items():
        if data.startswith(magic):
            return kind
    return None


def download(url: str, dest: Path, force: bool) -> tuple[bool, str]:
    if dest.exists() and not force and dest.stat().st_size > 1024:
        return True, "cached"
    last = ""
    for attempt in range(4):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = resp.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = str(exc)
            time.sleep(2 * (attempt + 1))
            continue
        kind = sniff(data)
        if kind is None:
            return False, f"not an image ({len(data)} bytes)"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return True, f"{len(data)} bytes {kind}"
    return False, f"fetch failed: {last}"


def optimize(src: Path, dest_base: Path, width: int) -> tuple[int, int]:
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        if im.width > width:
            height = round(im.height * width / im.width)
            im = im.resize((width, height), Image.LANCZOS)
        w, h = im.size
        im.save(dest_base.with_suffix(".webp"), "WEBP", quality=82, method=6)
        im.save(dest_base.with_suffix(".jpg"), "JPEG", quality=82, optimize=True, progressive=True)
    return w, h


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    entries = sources["entries"]
    if args.limit:
        entries = entries[: args.limit]

    table = load_cdx()
    MEDIA.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)

    manifest = []
    failures = []
    for entry in entries:
        time.sleep(1.0)
        ext = Path(urlparse(entry["url"]).path).suffix or ".jpg"
        raw = RAW / f"{entry['id']}{ext}"
        archive = archive_url(entry["url"], table)
        ok, note = download(archive, raw, args.force)
        if not ok:
            failures.append((entry["id"], note))
            print(f"FAIL {entry['id']}: {note}", file=sys.stderr)
            continue
        if raw.stat().st_size <= 1024:
            failures.append((entry["id"], "too small"))
            continue
        dest = MEDIA / entry["id"]
        try:
            w, h = optimize(raw, dest, ROLE_WIDTH[entry["role"]])
        except Exception as exc:  # noqa: BLE001
            failures.append((entry["id"], f"optimize failed: {exc}"))
            print(f"FAIL {entry['id']}: optimize {exc}", file=sys.stderr)
            continue
        manifest.append({
            **entry,
            "width": w,
            "height": h,
            "webp": f"/assets/media/{entry['id']}.webp",
            "jpg": f"/assets/media/{entry['id']}.jpg",
            "archive": archive,
        })
        print(f"OK   {entry['id']:<24} {w}x{h} {note}")

    (MEDIA / "manifest.json").write_text(
        json.dumps({"images": manifest}, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# Image credits",
        "",
        "Generated by `scripts/ghost-research/images.py`. Every image is real",
        "archived material from the official StarCraft: Ghost website, fetched",
        "through the Wayback Machine. No generated imagery. Downloaded files are",
        "gitignored; this metadata is tracked.",
        "",
        "| id | category | caption | credit | source | archive |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in manifest:
        lines.append(
            f"| `{item['id']}` | {item['category']} | {item['caption']} |"
            f" {item['credit']} | <{item['url']}> | <{item['archive']}> |"
        )
    lines.append("")
    if failures:
        lines.append("## Failed or unavailable")
        lines.append("")
        for image_id, note in failures:
            lines.append(f"- `{image_id}`: {note}")
        lines.append("")
    CREDITS.parent.mkdir(parents=True, exist_ok=True)
    CREDITS.write_text("\n".join(lines), encoding="utf-8")

    print(f"\n{len(manifest)} optimized, {len(failures)} failed")
    return 1 if failures and not manifest else 0


if __name__ == "__main__":
    raise SystemExit(main())
