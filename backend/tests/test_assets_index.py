# backend/tests/test_assets_index.py
"""The real curated index.json (schema, licence, provenance) and the offline search with Czech and English words."""

import json
from urllib.parse import urlsplit

import pytest

from app.assets import index, search
from app.assets.synonyms import expand

ROWS = json.loads(index.INDEX_FILE.read_text(encoding="utf-8"))
KEYS = {"id", "name", "tags", "category", "pack", "url", "license", "author", "source_page"}


def test_index_is_small_and_has_entries():
    assert 100 <= len(ROWS) <= 300
    assert index.INDEX_FILE.stat().st_size < 150_000


@pytest.mark.parametrize("row", ROWS, ids=[r["id"] for r in ROWS])
def test_every_entry_is_cc0_https_and_complete(row):
    assert KEYS <= set(row) <= KEYS | {"bytes"}
    assert row["license"] == "CC0-1.0"
    assert urlsplit(row["url"]).scheme == "https" and row["url"].endswith(".glb")
    assert urlsplit(row["source_page"]).scheme == "https"
    assert row["tags"] and all(isinstance(t, str) and t for t in row["tags"])
    assert row["name"] and row["author"] and row["pack"] and row["category"]
    assert index.ID_RE.fullmatch(row["id"])


def test_ids_are_unique_and_hosts_are_few():
    ids = [r["id"] for r in ROWS]
    assert len(set(ids)) == len(ids)
    assert index.allowed_hosts() == {"raw.githubusercontent.com"}


def test_get_rejects_malformed_and_unknown_ids():
    assert index.get(ROWS[0]["id"]) is not None
    for bad in ("../x", "A", "", None, 5, "qhome-chair-1/../../x", ROWS[0]["id"] + ".glb", "nope-nope"):
        assert index.get(bad) is None


@pytest.mark.parametrize("query,expected", [
    ("chair", "chair"), ("zidle", "chair"), ("stul", "table"), ("auto", "truck"), ("strom", "tree"),
    ("stromy", "tree"), ("dum", "house"), ("postel", "bed"), ("lednice", "fridge"), ("kun", "horse"),
])
def test_synonyms_find_the_english_model(query, expected):
    hits = search.find(query)
    assert hits, query
    assert any(expected in (a.name.lower() + " " + " ".join(a.tags)) for a in hits[:3]), [a.name for a in hits]


def test_exact_name_word_outranks_tag_match_and_limit_is_capped():
    hits = search.find("chair", limit=50)
    assert len(hits) <= search.MAX_LIMIT
    assert "chair" in hits[0].name.lower()


def test_category_filter_and_empty_query():
    cars = search.find("truck", category="vehicles")
    assert cars and all(a.category == "vehicles" for a in cars)
    assert search.find("chair", category="animals") == []
    assert search.find("   ") == []
    assert search.find("", category="animals")


def test_typo_still_finds_and_nonsense_finds_nothing():
    assert any("couch" in a.name.lower() for a in search.find("coutch"))
    assert search.find("qqqzzzxxx") == []


def test_expand_handles_diacritics_and_plurals():
    assert "chair" in expand("židle")
    assert "table" in expand("Stůl")
    assert "tree" in expand("trees")
