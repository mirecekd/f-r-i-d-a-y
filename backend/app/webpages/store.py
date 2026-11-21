# backend/app/webpages/store.py
"""Snapshots of fetched pages: <FRIDAY_DATA_DIR>/web/<id>/{meta.json,text.txt}; one snapshot per normalised URL (idempotent)."""

import hashlib
import json
import logging
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any

from app.deck import registry
from app.webpages import config
from app.webpages.urlguard import UrlRefused, ip_refusal, parse_target

log = logging.getLogger("friday.web")
ID_RE = re.compile(r"^[0-9a-f]{32}$")
DECK_TEXT_CHARS = 4000


def web_dir() -> Path:
    return Path(os.getenv("FRIDAY_DATA_DIR", "/srv/data")) / "web"


def normalise(url: str) -> str:
    """The URL a snapshot is keyed by: lower-case host, default port dropped, no fragment, no tracking parameters.
    Raises UrlRefused for anything the fetcher would refuse anyway."""
    target = parse_target(url, config.allowed_ports())
    if ":" in target.host or target.host.replace(".", "").isdigit():  # an IP literal: never store a private one
        if refused := ip_refusal(target.host):
            raise UrlRefused(refused)
    return target.url()


def web_id(url: str) -> str:
    return hashlib.sha256(normalise(url).encode()).hexdigest()[:32]


def load(page_id: str) -> dict[str, Any] | None:
    if not ID_RE.match(page_id):
        return None
    try:
        return json.loads((web_dir() / page_id / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def text_of(page_id: str) -> str:
    if not ID_RE.match(page_id):
        return ""
    return (web_dir() / page_id / "text.txt").read_text(encoding="utf-8")


def list_pages(limit: int = 30) -> list[dict[str, Any]]:
    folder = web_dir()
    paths = sorted(folder.glob("*/meta.json"), key=lambda p: p.stat().st_mtime, reverse=True) if folder.is_dir() else []
    return [m for p in paths[:limit] if (m := load(p.parent.name))]


def resolve(ref: object) -> dict[str, Any] | None:
    """Metadata for a full web id or a unique prefix of at least 8 hex characters."""
    text = str(ref or "").strip().lower()
    if ID_RE.match(text):
        return load(text)
    if re.fullmatch(r"[0-9a-f]{8,31}", text):
        hits = [m for m in list_pages(500) if m["id"].startswith(text)]
        return hits[0] if len(hits) == 1 else None
    return None


def save(url: str, fetched_bytes: int, content_type: str, extracted: dict[str, Any]) -> dict[str, Any]:
    """Write (or refresh) the snapshot of `url`, keep the fetch count, register the deck item; returns the metadata."""
    norm = normalise(url)
    page_id = hashlib.sha256(norm.encode()).hexdigest()[:32]
    folder = web_dir() / page_id
    folder.mkdir(parents=True, exist_ok=True)
    old = load(page_id) or {}
    stamp = int(time.time())
    host = norm.split("/")[2]
    meta = {
        "id": page_id, "url": norm, "host": host, "title": extracted["title"] or host, "canonical": extracted["canonical"],
        "site": extracted["site"], "author": extracted["author"], "published": extracted["published"],
        "description": extracted["description"], "lang": extracted["lang"], "outline": extracted["outline"],
        "truncated": extracted["truncated"], "chars": extracted["chars"], "bytes": fetched_bytes,
        "content_type": content_type, "fetched_at": stamp, "first_fetched_at": old.get("first_fetched_at", stamp),
        "fetch_count": int(old.get("fetch_count", 0)) + 1,
    }
    _write(folder / "text.txt", extracted["text"])
    _write(folder / "meta.json", json.dumps(meta, ensure_ascii=False))
    _register(meta, extracted["text"])
    return meta


def _write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _register(meta: dict[str, Any], text: str) -> None:
    """The deck must not break a save: failures are logged. A title the user renamed is kept by `register`."""
    try:
        registry.register(
            "web", meta["id"], meta["title"], meta["host"], size=meta["bytes"], source="tool",
            text=" ".join([meta["description"], text])[:DECK_TEXT_CHARS], created_at=meta["first_fetched_at"],
            meta={"url": meta["url"], "fetched_at": meta["fetched_at"], "bytes": meta["bytes"], "lang": meta["lang"],
                  "fetch_count": meta["fetch_count"]})
    except Exception as e:
        log.warning("deck registration of %s failed: %s: %s", meta["id"], type(e).__name__, e)


def delete(page_id: str) -> bool:
    if not ID_RE.match(page_id) or not (web_dir() / page_id).is_dir():
        return False
    shutil.rmtree(web_dir() / page_id, ignore_errors=True)
    return True
