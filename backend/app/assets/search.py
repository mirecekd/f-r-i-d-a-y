# backend/app/assets/search.py
"""Offline fuzzy search over name, tags and category of the asset index; Czech and English words."""

import re
from difflib import SequenceMatcher

from app.assets.index import Asset, load_index
from app.assets.synonyms import expand, fold

MAX_LIMIT = 8
FUZZY_MIN = 0.82


def _words(text: str) -> list[str]:
    return [w for w in re.split(r"[^a-z0-9]+", fold(text)) if w]


def _score_term(term: str, name_words: list[str], tags: set[str], category: str) -> float:
    if term in name_words:
        return 3.0
    if term in tags:
        return 2.0
    if term == category:
        return 1.5
    if len(term) >= 3 and any(w.startswith(term) for w in name_words):
        return 1.2
    if len(term) >= 3 and any(t.startswith(term) for t in tags):
        return 1.0
    if len(term) >= 4 and any(SequenceMatcher(None, term, w).ratio() >= FUZZY_MIN for w in name_words):
        return 0.8
    return 0.0


def score(asset: Asset, groups: list[set[str]]) -> float:
    """Sum over query words of the best score among the word and its synonyms; 0 means no query word matches."""
    name_words, tags = _words(asset.name), {fold(t) for t in asset.tags}
    category = fold(asset.category)
    return sum(max(_score_term(t, name_words, tags, category) for t in group) for group in groups)


def find(query: str, category: str | None = None, limit: int = MAX_LIMIT) -> list[Asset]:
    """Best matches first (ties: shorter name, then name). An empty query lists the category, if one is given."""
    limit = max(1, min(int(limit), MAX_LIMIT))
    groups = [expand(w) for w in _words(query)]
    wanted = fold(category).strip() if category else ""
    pool = [
        a for a in load_index().values()
        if not wanted or wanted == fold(a.category) or wanted in {fold(t) for t in a.tags}
    ]
    if not groups:
        return sorted(pool, key=lambda a: (len(a.name), a.name))[:limit] if wanted else []
    scored = [(score(a, groups), a) for a in pool]
    hits = [(s, a) for s, a in scored if s > 0]
    hits.sort(key=lambda sa: (-sa[0], len(sa[1].name), sa[1].name))
    return [a for _, a in hits[:limit]]
