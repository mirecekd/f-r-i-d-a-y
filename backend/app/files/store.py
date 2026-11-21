# backend/app/files/store.py
"""Non-image uploads in the uploads dir: <uuid>.bin original (never executed) + <uuid>.file.json metadata + <uuid>.txt text."""

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from app.vision.store import ID_RE, safe_name, uploads_dir

DOWNLOAD_RE = re.compile(r"^([0-9a-f]{32})$")


def download_url(file_id: str) -> str:
    return f"/api/files/{file_id}"


def save(raw: bytes, name: object, extracted: dict[str, Any]) -> dict[str, Any]:
    """Write original, extracted text and metadata; returns the metadata (tables and outline included)."""
    file_id = uuid.uuid4().hex
    folder = uploads_dir()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{file_id}.bin").write_bytes(raw)
    (folder / f"{file_id}.txt").write_text(extracted["text"], encoding="utf-8")
    meta = {
        "id": file_id, "is_file": True, "name": safe_name(name or "file"), "kind": extracted["kind"],
        "bytes": len(raw), "title": extracted["title"], "truncated": extracted["truncated"],
        "meta": extracted["meta"], "tables": extracted["tables"], "outline": extracted["outline"],
        "note": extracted.get("note"), "chars": len(extracted["text"]), "created": int(time.time()),
    }
    path = folder / f"{file_id}.file.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False))
    tmp.replace(path)
    return meta


def load(file_id: str) -> dict[str, Any] | None:
    if not ID_RE.match(file_id):
        return None
    try:
        return json.loads((uploads_dir() / f"{file_id}.file.json").read_text())
    except (OSError, ValueError):
        return None


def text_of(file_id: str) -> str:
    return (uploads_dir() / f"{file_id}.txt").read_text(encoding="utf-8")


def original_path(file_id: str) -> Path | None:
    if not DOWNLOAD_RE.match(file_id):
        return None
    path = uploads_dir() / f"{file_id}.bin"
    return path if path.is_file() else None


def list_files(limit: int = 30) -> list[dict[str, Any]]:
    folder = uploads_dir()
    paths = sorted(folder.glob("*.file.json"), key=lambda p: p.stat().st_mtime, reverse=True) if folder.is_dir() else []
    return [m for p in paths[:limit] if (m := load(p.name.split(".")[0]))]


def resolve(ref: object) -> dict[str, Any] | None:
    """Metadata for a full file id or a unique prefix of at least 8 hex characters."""
    text = str(ref or "").strip().lower()
    if ID_RE.match(text):
        return load(text)
    if re.fullmatch(r"[0-9a-f]{8,31}", text):
        hits = [m for m in list_files(500) if m["id"].startswith(text)]
        return hits[0] if len(hits) == 1 else None
    return None


