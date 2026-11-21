# backend/app/deck/query.py
"""Read side of the deck: list, count, get and stats (fixed parameterised statements, no SQL built at runtime)."""

import json
import sqlite3
from typing import Any

from app.deck import db, fts
from app.deck.items import TYPES, DeckError, row_to_item

MAX_LIMIT = 200
# Both statements share one literal filter (no SQL is built at runtime). A NULL parameter switches a filter off.
# `wide` searches all text columns (no FTS); `rowids` are the FTS hits, which match in addition to the title test.
LIST_SQL = """SELECT * FROM items WHERE
  (:type IS NULL OR type = :type)
  AND (:tag IS NULL OR EXISTS (SELECT 1 FROM json_each(items.tags) WHERE lower(value) = lower(:tag)))
  AND (:pinned IS NULL OR pinned = :pinned)
  AND (:words IS NULL
       OR rowid IN (SELECT value FROM json_each(:rowids))
       OR NOT EXISTS (SELECT 1 FROM json_each(:words) AS w WHERE instr(lower(
            CASE WHEN :wide THEN title || ' ' || subtitle || ' ' || tags || ' ' || text ELSE title END),
            lower(w.value)) = 0))
ORDER BY pinned DESC, updated_at DESC, rowid DESC
LIMIT :limit OFFSET :offset"""
COUNT_SQL = """SELECT COUNT(*) FROM items WHERE
  (:type IS NULL OR type = :type)
  AND (:tag IS NULL OR EXISTS (SELECT 1 FROM json_each(items.tags) WHERE lower(value) = lower(:tag)))
  AND (:pinned IS NULL OR pinned = :pinned)
  AND (:words IS NULL
       OR rowid IN (SELECT value FROM json_each(:rowids))
       OR NOT EXISTS (SELECT 1 FROM json_each(:words) AS w WHERE instr(lower(
            CASE WHEN :wide THEN title || ' ' || subtitle || ' ' || tags || ' ' || text ELSE title END),
            lower(w.value)) = 0))
"""


def _params(
    conn: sqlite3.Connection, type_: str | None, q: str | None, tag: str | None, pinned: bool | None
) -> dict[str, Any]:
    if type_ and type_ not in TYPES:
        raise DeckError(f"unknown type {type_!r}; expected one of {list(TYPES)}")
    words = fts.words_of(q)
    rowids = fts.hit_rowids(conn, words)
    return {
        "type": type_ or None,
        "tag": tag or None,
        "pinned": None if pinned is None else int(bool(pinned)),
        "words": json.dumps(words) if words else None,
        "rowids": json.dumps(rowids),
        "wide": 0 if db.has_fts(conn) else 1,
    }


def _bounded(value: object, default: int, low: int, high: int) -> int:
    """An int clamped to [low, high]; anything that is not a plain number (text, None, nan, lists) gives `default`."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
        return default
    return max(low, min(int(value), high))


def list_items(
    type: str | None = None,
    q: str | None = None,
    tag: str | None = None,
    pinned: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Items pinned first, then newest first."""
    with db.read() as conn:
        params = _params(conn, type, q, tag, pinned) | {
            "limit": _bounded(limit, 50, 1, MAX_LIMIT),
            "offset": _bounded(offset, 0, 0, 10_000_000),
        }
        return [row_to_item(r) for r in conn.execute(LIST_SQL, params).fetchall()]


def count_items(
    type: str | None = None, q: str | None = None, tag: str | None = None, pinned: bool | None = None
) -> int:
    with db.read() as conn:
        return conn.execute(COUNT_SQL, _params(conn, type, q, tag, pinned)).fetchone()[0]


def get(deck_id: str) -> dict[str, Any] | None:
    with db.read() as conn:
        row = conn.execute("SELECT * FROM items WHERE id = ?", (str(deck_id),)).fetchone()
    return row_to_item(row) if row else None


def find(type: str, ref_id: str) -> dict[str, Any] | None:
    with db.read() as conn:
        row = conn.execute("SELECT * FROM items WHERE type = ? AND ref_id = ?", (type, ref_id)).fetchone()
    return row_to_item(row) if row else None


def resolve(ref: object) -> dict[str, Any] | None:
    """An item by full deck id or a unique prefix of at least 4 characters."""
    text = str(ref or "").strip()
    found = get(text)
    if found or len(text) < 4:
        return found
    with db.read() as conn:
        rows = conn.execute("SELECT * FROM items WHERE substr(id, 1, ?) = ? LIMIT 2", (len(text), text)).fetchall()
    return row_to_item(rows[0]) if len(rows) == 1 else None


def stats() -> dict[str, Any]:
    with db.read() as conn:
        by_type = {r["type"]: r["n"] for r in conn.execute("SELECT type, COUNT(*) AS n FROM items GROUP BY type")}
        pinned = conn.execute("SELECT COUNT(*) FROM items WHERE pinned = 1").fetchone()[0]
    return {"total": sum(by_type.values()), "by_type": by_type, "pinned": pinned}
