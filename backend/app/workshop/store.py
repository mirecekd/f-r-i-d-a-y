# backend/app/workshop/store.py
"""Workshop persistence: <FRIDAY_DATA_DIR>/workshops/<id>.json, atomic writes and origin allocation."""

import json
import os
import re
import secrets
import time
from pathlib import Path
from typing import Any

ID_RE = re.compile(r"^[0-9a-f]{12}$")
MAX_HISTORY = 50
MAX_SOURCES = 12
ORIGIN_SPACING = 400.0  # workshop n lives at (0, 0, 400 * n), far away from the desk
DEFAULT_TITLE = "Nova dilna"


class WorkshopError(ValueError):
    """A workshop request that is malformed or refers to an unknown workshop."""


def workshops_dir() -> Path:
    return Path(os.getenv("FRIDAY_DATA_DIR", "/srv/data")) / "workshops"


def valid_id(value: object) -> bool:
    return isinstance(value, str) and ID_RE.match(value) is not None


def origin_of(n: int) -> tuple[float, float, float]:
    return (0.0, 0.0, ORIGIN_SPACING * n)


def _path(workshop_id: str) -> Path:
    if not valid_id(workshop_id):
        raise WorkshopError(f"workshop id {str(workshop_id)[:40]!r} is not a 12 character hex id")
    return workshops_dir() / f"{workshop_id}.json"


def _clean_sources(raw: object) -> list[str]:
    """Deck ids of the reference items around the table; older files have none."""
    ids = [s for s in raw if isinstance(s, str) and s] if isinstance(raw, list) else []
    return list(dict.fromkeys(ids))[:MAX_SOURCES]


def _clean(raw: object, workshop_id: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("id") != workshop_id:
        raise WorkshopError(f"workshop file {workshop_id} is damaged")
    n = raw.get("origin_n")
    spec = raw.get("spec")
    return {
        "id": workshop_id,
        "title": str(raw.get("title") or DEFAULT_TITLE),
        "spec": spec if isinstance(spec, dict) else None,
        "values": raw.get("values") if isinstance(raw.get("values"), dict) else {},
        "history": [s for s in raw.get("history") or [] if s is None or isinstance(s, dict)][-MAX_HISTORY:],
        "redo": [s for s in raw.get("redo") or [] if s is None or isinstance(s, dict)][-MAX_HISTORY:],
        "sources": _clean_sources(raw.get("sources")),
        "origin_n": n if isinstance(n, int) and not isinstance(n, bool) and n >= 1 else 1,
        "created": raw.get("created") if isinstance(raw.get("created"), (int, float)) else int(time.time()),
    }


def exists(workshop_id: str) -> bool:
    return valid_id(workshop_id) and _path(workshop_id).is_file()


def load(workshop_id: str) -> dict[str, Any]:
    path = _path(workshop_id)
    if not path.is_file():
        raise WorkshopError(f"unknown workshop '{workshop_id}'")
    try:
        return _clean(json.loads(path.read_text(encoding="utf-8")), workshop_id)
    except (OSError, ValueError) as e:  # unreadable or corrupt file: report it instead of crashing
        raise WorkshopError(f"cannot read workshop '{workshop_id}': {e}") from e


def save(rec: dict[str, Any]) -> None:
    """Write the record atomically (temp file + rename); history and redo are capped at 50 specs."""
    rec["history"], rec["redo"] = rec["history"][-MAX_HISTORY:], rec["redo"][-MAX_HISTORY:]
    rec["updated"] = int(time.time())
    path = _path(rec["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(rec, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    os.replace(tmp, path)


def list_ids() -> list[str]:
    folder = workshops_dir()
    return sorted(p.stem for p in folder.glob("*.json") if valid_id(p.stem)) if folder.is_dir() else []


def free_origin_n() -> int:
    """The lowest n >= 1 that no stored workshop uses."""
    used: set[int] = set()
    for workshop_id in list_ids():
        try:
            used.add(load(workshop_id)["origin_n"])
        except WorkshopError:
            continue
    n = 1
    while n in used:
        n += 1
    return n


def create(title: str | None = None) -> dict[str, Any]:
    """A new empty workshop with its own origin, already on disk."""
    rec = {
        "id": secrets.token_hex(6),
        "title": (title or "").strip()[:120] or DEFAULT_TITLE,
        "spec": None,
        "values": {},
        "history": [],
        "redo": [],
        "sources": [],
        "origin_n": free_origin_n(),
        "created": int(time.time()),
    }
    save(rec)
    return rec


def delete(workshop_id: str) -> bool:
    path = _path(workshop_id)
    had = path.is_file()
    path.unlink(missing_ok=True)
    return had
