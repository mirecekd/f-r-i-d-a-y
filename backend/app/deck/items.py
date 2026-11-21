# backend/app/deck/items.py
"""Deck item vocabulary and the row <-> dict conversion."""

import hashlib
import json
import sqlite3
import time
from typing import Any

TYPES = ("image", "file", "model3d", "scene", "note", "view", "memory_graph", "web", "workshop")
SOURCES = ("upload", "generated", "derived", "tool")
SOURCE_RANK = {"upload": 0, "generated": 1, "tool": 2, "derived": 3}  # on re-register the stronger source wins
MAX_TITLE, MAX_SUBTITLE, MAX_TEXT, MAX_TAGS, MAX_TAG, MAX_META = 200, 300, 4000, 20, 40, 100_000


class DeckError(ValueError):
    """A deck request that is malformed or refers to an unknown item."""


def item_id(type_: str, ref_id: str) -> str:
    """Deterministic deck id of (type, ref_id): callers can name a parent before it is registered."""
    return "d" + hashlib.sha256(f"{type_}:{ref_id}".encode()).hexdigest()[:15]


def now() -> int:
    return int(time.time())


def clean_tags(tags: object) -> list[str]:
    """Trimmed, de-duplicated (case-insensitive), at most 20 tags of 40 characters."""
    if isinstance(tags, str):
        tags = [t for t in tags.replace(";", ",").split(",")]
    out: list[str] = []
    seen: set[str] = set()
    for tag in tags if isinstance(tags, (list, tuple)) else []:
        text = " ".join(str(tag).split())[:MAX_TAG]
        if text and text.lower() not in seen:
            seen.add(text.lower())
            out.append(text)
    return out[:MAX_TAGS]


def dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def loads(text: str, default: Any) -> Any:
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return default


def row_to_item(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"], "type": row["type"], "title": row["title"], "subtitle": row["subtitle"],
        "ref_id": row["ref_id"], "created_at": row["created_at"], "updated_at": row["updated_at"], "size": row["size"],
        "tags": loads(row["tags"], []), "pinned": bool(row["pinned"]), "thumb_url": row["thumb_url"],
        "source": row["source"], "parent_ids": loads(row["parent_ids"], []), "meta": loads(row["meta"], {}),
    }
