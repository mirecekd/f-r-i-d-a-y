# backend/app/deck/registry.py
"""Write side of the deck: the stable `register` entry point, update and delete."""

import logging
import sqlite3
from typing import Any

from app.deck import db, fts, notify
from app.deck.items import (
    MAX_META,
    MAX_SUBTITLE,
    MAX_TEXT,
    MAX_TITLE,
    SOURCE_RANK,
    SOURCES,
    TYPES,
    DeckError,
    clean_tags,
    dumps,
    item_id,
    loads,
    now,
)
from app.deck.query import get

log = logging.getLogger("friday.deck")


def _parents(parent_ids: object) -> list[str]:
    return [str(p)[:64] for p in parent_ids][:50] if isinstance(parent_ids, (list, tuple)) else []


def register(type: str, ref_id: str, title: str, subtitle: str = "", *, size: int = 0, tags: list[str] | None = None,
             thumb_url: str | None = None, source: str = "generated", parent_ids: list[str] | None = None,
             meta: dict[str, Any] | None = None, text: str = "", created_at: int | None = None) -> str:
    """Add or refresh the deck item for (type, ref_id) and return its deck id. STABLE API for every builder.

    Idempotent: a second call with the same (type, ref_id) updates the item in place. A title the user renamed is kept,
    tags are merged, `pinned` is never touched, `parent_ids` are merged, and the source never gets weaker
    (upload < generated < tool < derived). `parent_ids` hold DECK ids of the originals; `item_id(type, ref_id)` gives the
    deck id of an item without a lookup. Never raises on bad optional data; raises DeckError for an unknown type/source."""
    if type not in TYPES:
        raise DeckError(f"unknown deck type {type!r}; expected one of {list(TYPES)}")
    if source not in SOURCES:
        raise DeckError(f"unknown deck source {source!r}; expected one of {list(SOURCES)}")
    ref_id = str(ref_id)[:200]
    deck_id, stamp = item_id(type, ref_id), now()
    title = (str(title).strip() or ref_id)[:MAX_TITLE]
    with db.write() as conn:
        old = conn.execute("SELECT * FROM items WHERE id = ?", (deck_id,)).fetchone()
        if old is None:
            conn.execute(
                "INSERT INTO items (id, type, title, subtitle, ref_id, created_at, updated_at, size, tags, thumb_url, source,"
                " parent_ids, meta, text) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (deck_id, type, title, str(subtitle)[:MAX_SUBTITLE], ref_id, created_at or stamp, stamp, max(0, int(size)),
                 dumps(clean_tags(tags)), thumb_url, source, dumps(_parents(parent_ids)), _meta(meta), str(text)[:MAX_TEXT]))
        else:
            _refresh(conn, old, title, subtitle, size, tags, thumb_url, source, parent_ids, meta, text, stamp)
        fts.index(conn, deck_id)
    notify.notify(deck_id)
    return deck_id


def _meta(meta: object) -> str:
    text = dumps(meta if isinstance(meta, dict) else {})
    return text if len(text) <= MAX_META else "{}"


def _refresh(conn: sqlite3.Connection, old: sqlite3.Row, title: str, subtitle: str, size: int, tags: list[str] | None,
             thumb_url: str | None, source: str, parent_ids: list[str] | None, meta: dict[str, Any] | None,
             text: str, stamp: int) -> None:
    kept_title = old["title"] if old["title_locked"] else title
    merged_tags = clean_tags([*loads(old["tags"], []), *(tags or [])])
    merged_parents = _parents([*loads(old["parent_ids"], []), *(parent_ids or [])])
    merged_parents = list(dict.fromkeys(merged_parents))
    stronger = source if SOURCE_RANK[source] > SOURCE_RANK.get(old["source"], 0) else old["source"]
    conn.execute(
        "UPDATE items SET title=?, subtitle=?, updated_at=?, size=?, tags=?, thumb_url=?, source=?, parent_ids=?, meta=?,"
        " text=? WHERE id=?",
        (kept_title, str(subtitle)[:MAX_SUBTITLE] or old["subtitle"], stamp, max(0, int(size)) or old["size"],
         dumps(merged_tags), thumb_url or old["thumb_url"], stronger, dumps(merged_parents),
         _meta(meta) if meta else old["meta"], str(text)[:MAX_TEXT] or old["text"], old["id"]))


def update(deck_id: str, *, title: str | None = None, tags: object = None, pinned: bool | None = None) -> dict[str, Any]:
    """Change title (locks it against later `register` renames), tags (replace) or pinned; returns the item."""
    with db.write() as conn:
        row = conn.execute("SELECT * FROM items WHERE id = ?", (str(deck_id),)).fetchone()
        if row is None:
            raise DeckError(f"unknown deck item {deck_id!r}")
        if title is not None:
            new_title = str(title).strip()[:MAX_TITLE]
            if not new_title:
                raise DeckError("title must not be empty")
            conn.execute("UPDATE items SET title = ?, title_locked = 1 WHERE id = ?", (new_title, row["id"]))
        if tags is not None:
            conn.execute("UPDATE items SET tags = ? WHERE id = ?", (dumps(clean_tags(tags)), row["id"]))
        if pinned is not None:
            conn.execute("UPDATE items SET pinned = ? WHERE id = ?", (1 if pinned else 0, row["id"]))
        conn.execute("UPDATE items SET updated_at = ? WHERE id = ?", (now(), row["id"]))
        fts.index(conn, row["id"])
    notify.notify(row["id"])
    item = get(row["id"])
    assert item is not None
    return item


def delete(deck_id: str, delete_stored: bool = False) -> bool:
    """Remove the registry row (True when it existed). The stored file/model is kept unless `delete_stored` is set;
    the caller must have the user's approval for that. Children keep their `parent_ids` (provenance stays readable)."""
    with db.write() as conn:
        row = conn.execute("SELECT rowid, type, ref_id FROM items WHERE id = ?", (str(deck_id),)).fetchone()
        if row is None:
            return False
        conn.execute("DELETE FROM items WHERE id = ?", (str(deck_id),))
        fts.unindex(conn, row["rowid"])
    if delete_stored:
        from app.deck import stored

        stored.delete_stored(row["type"], row["ref_id"])
    notify.notify(str(deck_id))
    return True


def prune(type: str, keep: int) -> int:
    """Drop the oldest unpinned registry rows of `type` beyond `keep` (registry rows only); returns how many went."""
    with db.write() as conn:
        rows = conn.execute(
            "SELECT rowid, id FROM items WHERE type = ? AND pinned = 0 ORDER BY updated_at DESC, rowid DESC LIMIT -1 OFFSET ?",
            (type, max(0, keep))).fetchall()
        for row in rows:
            conn.execute("DELETE FROM items WHERE rowid = ?", (row["rowid"],))
            fts.unindex(conn, row["rowid"])
    for row in rows:
        notify.notify(row["id"])
    return len(rows)
