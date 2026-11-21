# backend/app/deck/fts.py
"""Full-text index of the deck (FTS5 when available) and the search parameters with a substring fallback."""

import re
import sqlite3

from app.deck import db

_WORD = re.compile(r"[^\W_]+", re.UNICODE)
MAX_HITS = 5000


def index(conn: sqlite3.Connection, deck_id: str) -> None:
    """(Re)write the FTS row of one item; the FTS rowid is the items rowid."""
    if not db.has_fts(conn):
        return
    row = conn.execute("SELECT rowid, title, subtitle, tags, text FROM items WHERE id = ?", (deck_id,)).fetchone()
    if row is None:
        return
    conn.execute("DELETE FROM deck_fts WHERE rowid = ?", (row["rowid"],))
    conn.execute("INSERT INTO deck_fts (rowid, title, subtitle, tags, text) VALUES (?, ?, ?, ?, ?)",
                 (row["rowid"], row["title"], row["subtitle"], row["tags"], row["text"]))


def unindex(conn: sqlite3.Connection, rowid: int) -> None:
    if db.has_fts(conn):
        conn.execute("DELETE FROM deck_fts WHERE rowid = ?", (rowid,))


def words_of(query: str | None) -> list[str]:
    return _WORD.findall(query or "")[:8]


def hit_rowids(conn: sqlite3.Connection, words: list[str]) -> list[int]:
    """Rowids of items matching every word as a prefix in the FTS index; empty without FTS."""
    if not words or not db.has_fts(conn):
        return []
    match = " ".join(f'"{w}"*' for w in words)
    rows = conn.execute("SELECT rowid FROM deck_fts WHERE deck_fts MATCH ? LIMIT ?", (match, MAX_HITS)).fetchall()
    return [r[0] for r in rows]
