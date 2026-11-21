# backend/app/deck/db.py
"""SQLite connection, schema and version table of the deck registry (<FRIDAY_DATA_DIR>/deck.db)."""

import logging
import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

log = logging.getLogger("friday.deck")
SCHEMA_VERSION = 1
_ready: set[str] = set()
_init_lock = threading.Lock()

_V1 = """
CREATE TABLE IF NOT EXISTS items (
  id TEXT PRIMARY KEY, type TEXT NOT NULL, title TEXT NOT NULL, subtitle TEXT NOT NULL DEFAULT '',
  ref_id TEXT NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL, size INTEGER NOT NULL DEFAULT 0,
  tags TEXT NOT NULL DEFAULT '[]', pinned INTEGER NOT NULL DEFAULT 0, thumb_url TEXT,
  source TEXT NOT NULL DEFAULT 'generated', parent_ids TEXT NOT NULL DEFAULT '[]', meta TEXT NOT NULL DEFAULT '{}',
  text TEXT NOT NULL DEFAULT '', title_locked INTEGER NOT NULL DEFAULT 0, UNIQUE (type, ref_id)
);
CREATE INDEX IF NOT EXISTS items_type ON items (type, updated_at);
CREATE INDEX IF NOT EXISTS items_updated ON items (updated_at);
"""
_FTS = ("CREATE VIRTUAL TABLE IF NOT EXISTS deck_fts USING fts5"
        "(title, subtitle, tags, text, tokenize='unicode61 remove_diacritics 2');")


def db_path() -> Path:
    return Path(os.getenv("FRIDAY_DATA_DIR", "/srv/data")) / "deck.db"


def has_fts(conn: sqlite3.Connection) -> bool:
    """True when the FTS5 index exists and is not switched off by FRIDAY_DECK_NO_FTS (used by the tests)."""
    if os.getenv("FRIDAY_DECK_NO_FTS"):
        return False
    return conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'deck_fts'").fetchone() is not None


def _init(conn: sqlite3.Connection) -> None:
    """Idempotent setup (every statement is IF NOT EXISTS), so racing processes cannot break it."""
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] or 0
    if version > SCHEMA_VERSION:
        raise RuntimeError(f"deck.db has schema version {version}; this build understands {SCHEMA_VERSION}")
    if version < 1:
        conn.executescript(_V1)
        conn.execute("INSERT INTO schema_version (version) SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM schema_version)")
    if not os.getenv("FRIDAY_DECK_NO_FTS"):
        try:
            conn.executescript(_FTS)
        except sqlite3.OperationalError as e:
            log.warning("deck: FTS5 unavailable (%s); search falls back to LIKE", e)


def connect() -> sqlite3.Connection:
    """A new autocommit connection (one per operation: safe from any thread); the schema is created on first use."""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    key = str(path)
    if key not in _ready:
        with _init_lock:
            if key not in _ready:
                _init(conn)
                _ready.add(key)
    return conn


@contextmanager
def read() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def write() -> Iterator[sqlite3.Connection]:
    """One immediate transaction: concurrent writers queue up on the busy timeout instead of failing."""
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")
    finally:
        conn.close()
