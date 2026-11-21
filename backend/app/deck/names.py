# backend/app/deck/names.py
"""Find deck items by NAME: case-insensitive, accents folded, extension optional ('architect' finds 'architect.webp')."""

import difflib
import json
import re
import unicodedata
from typing import Any

from app.deck import backfill, db
from app.deck.items import TYPES, DeckError, row_to_item

_EXT = re.compile(r"\.[A-Za-z0-9]{1,5}$")
_SEP = re.compile(r"[\W_]+", re.UNICODE)
MIN_MATCH = 36  # weakest score deck_find lists (a typo-level match)
MIN_RESOLVE = 60  # weakest score other tools accept as "this is the file the user means"
EXACT = 95


def fold(text: object) -> str:
    """Lower case, accents removed, every run of punctuation or space one blank."""
    plain = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return _SEP.sub(" ", plain.lower()).strip()


def _stem(name: str) -> str:
    return _EXT.sub("", name.strip())


def names_of(item: dict[str, Any]) -> list[str]:
    """The names a user may call the item by: its title and, for files and images, the original file name."""
    stored = item["meta"].get("name")
    return [n for n in (item["title"], stored if isinstance(stored, str) else None) if n]


def score(query: str, names: list[str]) -> int:
    """0-100: 100 same name, 95 same name without extension, 80 prefix, 70 all words, 60 substring, below that typos."""
    q, q_stem = fold(query), fold(_stem(query))
    if not q_stem:
        return 0
    best = 0
    for name in names:
        n, n_stem = fold(name), fold(_stem(name))
        if q == n:
            best = max(best, 100)
        elif q_stem == n_stem:
            best = max(best, EXACT)
        elif n_stem.startswith(q_stem) or n.startswith(q):
            best = max(best, 80)
        elif all(any(w.startswith(t) for w in n.split()) for t in q_stem.split()):
            best = max(best, 70)
        elif q_stem in n:
            best = max(best, 60)
        else:
            best = max(best, int(difflib.SequenceMatcher(None, q_stem, n_stem).ratio() * 50))
    return best


def candidates(types: list[str] | None) -> list[dict[str, Any]]:
    bad = [t for t in types or [] if t not in TYPES]
    if bad:
        raise DeckError(f"unknown type {bad[0]!r}; expected one of {list(TYPES)}")
    backfill.ensure()
    with db.read() as conn:
        rows = conn.execute(
            "SELECT * FROM items WHERE (:types IS NULL OR type IN (SELECT value FROM json_each(:types)))",
            {"types": json.dumps(types) if types else None},
        ).fetchall()
    return [row_to_item(r) for r in rows]


def find_by_name(query: str, types: list[str] | None = None, limit: int = 8) -> list[dict[str, Any]]:
    """Best matches first: [{**item, 'score': n}]; ties go to the newest item."""
    scored = [(score(query, names_of(i)), i) for i in candidates(types)]
    hits = [{**i, "score": s} for s, i in scored if s >= MIN_MATCH]
    hits.sort(key=lambda h: (h["score"], h["updated_at"]), reverse=True)
    return hits[: max(1, limit)]


def resolve_name(ref: object, type_: str) -> tuple[str | None, str | None]:
    """The ref_id of the one `type_` item the name `ref` means, or (None, error) when it is ambiguous.

    (None, None) means nothing matched: the caller reports its own unknown-id error."""
    if not isinstance(ref, str) or not ref.strip():
        return None, None
    hits = [h for h in find_by_name(ref, [type_], 20) if h["score"] >= MIN_RESOLVE]
    if not hits:
        return None, None
    if len(hits) == 1 or (hits[0]["score"] >= EXACT and hits[1]["score"] < hits[0]["score"]):
        return hits[0]["ref_id"], None
    listed = "; ".join(f"{h['title']} (id {h['ref_id'][:8]})" for h in hits[:5])
    return None, f"'{ref[:60]}' matches several {type_}s: {listed}. Use the id."


def resolve_stored(ref: object, type_: str, by_id: Any) -> tuple[dict[str, Any] | None, str | None]:
    """The stored item `ref` means: by id (`by_id(ref)`), else by NAME through the deck. Returns (meta, error)."""
    meta = by_id(ref)
    if meta is not None:
        return meta, None
    ref_id, error = resolve_name(ref, type_)
    return (by_id(ref_id), None) if ref_id else (None, error)
