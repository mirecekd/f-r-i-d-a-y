# backend/app/vision/store.py
"""Uploaded images on disk: <uuid>.<ext> original, <uuid>.analysis.jpg downscaled copy, <uuid>.json metadata."""

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from app.vision.images import EXT_BY_MIME, Inspected

ID_RE = re.compile(r"^[0-9a-f]{32}$")
FILE_RE = re.compile(r"^([0-9a-f]{32})\.(jpg|png|webp|gif)$")
_NAME_JUNK = re.compile(r"[\x00-\x1f\x7f/\\]")


def uploads_dir() -> Path:
    return Path(os.getenv("FRIDAY_DATA_DIR", "/srv/data")) / "uploads"


def safe_name(name: object) -> str:
    return _NAME_JUNK.sub("", str(name or "")).strip()[:100] or "image"


def url_of(meta: dict[str, Any]) -> str:
    return f"/api/uploads/{meta['id']}.{meta['ext']}"


def save(raw: bytes, name: object, insp: Inspected) -> dict[str, Any]:
    """Write the untouched original, the analysis copy and the metadata; returns the metadata."""
    image_id, ext = uuid.uuid4().hex, EXT_BY_MIME[insp.mime]
    folder = uploads_dir()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{image_id}.{ext}").write_bytes(raw)
    (folder / f"{image_id}.analysis.jpg").write_bytes(insp.analysis_jpeg)
    meta = {
        "id": image_id, "ext": ext, "mime": insp.mime, "name": safe_name(name), "bytes": len(raw),
        "w": insp.w, "h": insp.h, "exif": insp.exif, "created": int(time.time()), "analysis": None,
    }
    write_meta(meta)
    return meta


def write_meta(meta: dict[str, Any]) -> None:
    path = uploads_dir() / f"{meta['id']}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False))
    tmp.replace(path)


def load_meta(image_id: str) -> dict[str, Any] | None:
    if not ID_RE.match(image_id):
        return None
    try:
        return json.loads((uploads_dir() / f"{image_id}.json").read_text())
    except (OSError, ValueError):
        return None


def list_meta(limit: int = 50) -> list[dict[str, Any]]:
    folder = uploads_dir()
    paths = sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if folder.is_dir() else []
    metas = [m for p in paths[:limit] if (m := load_meta(p.stem))]
    return metas


def resolve(ref: object) -> dict[str, Any] | None:
    """Metadata for a full image id or a unique prefix of at least 8 hex characters."""
    text = str(ref or "").strip().lower().split(".")[0]
    if ID_RE.match(text):
        return load_meta(text)
    if re.fullmatch(r"[0-9a-f]{8,31}", text):
        hits = [m for m in list_meta(500) if m["id"].startswith(text)]
        return hits[0] if len(hits) == 1 else None
    return None


def analysis_jpeg(image_id: str) -> bytes:
    return (uploads_dir() / f"{image_id}.analysis.jpg").read_bytes()
