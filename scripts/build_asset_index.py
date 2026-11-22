# scripts/build_asset_index.py
"""Regenerate backend/app/assets/index.json from scripts/asset_packs.json (the pack manifest: one record per CC0 pack with
its author, licence evidence, source page, base url and file list). Every file is probed with a ranged GET: only urls that
answer 200/206 and start with the glTF magic are kept, anything else is dropped (never invented).

Usage: python3 scripts/build_asset_index.py [--offline]   (--offline keeps all manifest files without probing)"""

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "scripts" / "asset_packs.json"
OUT = ROOT / "backend" / "app" / "assets" / "index.json"
MAX_ENTRIES = 300


def words(stem: str) -> list[str]:
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", stem.replace("%20", " "))
    return [w.lower() for w in re.split(r"[\s_\-]+", spaced) if w and not w.isdigit()]


def probe(url: str) -> int | None:
    """Size in bytes when the url serves a glTF binary (magic checked on a ranged request), else None."""
    if not url.startswith("https://"):
        return None
    try:
        req = Request(url, headers={"Range": "bytes=0-11", "User-Agent": "FridayAssetIndex/1"})
        with urlopen(req, timeout=20) as resp:  # noqa: S310 - scheme checked above
            head = resp.read(12)
            total = (resp.headers.get("Content-Range") or "").rpartition("/")[2]
            size = int(total) if total.isdigit() else int(resp.headers.get("Content-Length") or 0)
    except (OSError, ValueError):
        return None
    return size or None if head[:4] == b"glTF" else None


def entry(pack: dict, filename: str, size: int | None) -> dict:
    stem = filename.rsplit(".", 1)[0]
    name = " ".join(words(stem)).title() or stem
    category = pack["category"]
    tags = set(words(stem)) | set(pack.get("tags", []))
    for pattern, label in pack.get("categories", {}).items():
        if re.search(pattern, stem, re.IGNORECASE):
            tags |= set(words(label))
            break
    item = {
        "id": f"{pack['id']}-{re.sub(r'[^a-z0-9]+', '-', stem.lower()).strip('-')}",
        "name": name,
        "tags": sorted(tags),
        "category": category,
        "pack": pack["name"],
        "url": pack["base_url"] + filename,
        "license": pack["license"],
        "author": pack["author"],
        "source_page": pack["source_page"],
    }
    if size:
        item["bytes"] = size
    return item


def main(argv: list[str]) -> int:
    packs = json.loads(MANIFEST.read_text(encoding="utf-8"))
    jobs = [(p, f) for p in packs for f in p["files"]]
    offline = "--offline" in argv
    with ThreadPoolExecutor(12) as pool:
        sizes = [0] * len(jobs) if offline else list(pool.map(lambda j: probe(j[0]["base_url"] + j[1]), jobs))
    items, dropped = [], []
    for (pack, filename), size in zip(jobs, sizes, strict=True):
        (items if size is not None else dropped).append(entry(pack, filename, size) if size is not None else filename)
    if len(items) > MAX_ENTRIES:
        print(f"too many entries: {len(items)} > {MAX_ENTRIES}", file=sys.stderr)
        return 1
    ids = [i["id"] for i in items]
    if len(set(ids)) != len(ids):
        print("duplicate ids", file=sys.stderr)
        return 1
    OUT.write_text(json.dumps(items, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    per_pack = {p["name"]: sum(1 for i in items if i["pack"] == p["name"]) for p in packs}
    print(f"{len(items)} entries kept, {len(dropped)} dropped: {dropped}")
    print(json.dumps(per_pack, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
