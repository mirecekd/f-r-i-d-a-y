# backend/tests/test_deck_registry.py
"""Deck registry: idempotent register, search with and without FTS, provenance, pin/tag, delete semantics, versions, threads."""

import sqlite3
import threading

import pytest

from app import deck
from app.deck import db


def got(deck_id: str) -> dict:
    """The deck item, failing the test when it is missing (keeps the type checker honest)."""
    item = deck.get(deck_id)
    assert item is not None, f"deck item {deck_id} is missing"
    return item


def test_register_is_idempotent_and_keeps_user_edits():
    first = deck.register("file", "f1", "Report", "pdf", tags=["a"], source="upload", text="alpha")
    deck.update(first, title="My report", pinned=True)
    again = deck.register("file", "f1", "Report v2", "pdf, 3 pages", tags=["B", "a"], source="generated")
    item = deck.get(first)
    assert again == first == deck.item_id("file", "f1") and deck.count_items() == 1
    assert item and item["title"] == "My report" and item["pinned"] and item["tags"] == ["a", "B"]
    assert item["subtitle"] == "pdf, 3 pages" and item["source"] == "generated"  # the stronger source wins


def test_unknown_type_and_source_are_rejected():
    with pytest.raises(deck.DeckError):
        deck.register("movie", "x", "x")
    with pytest.raises(deck.DeckError):
        deck.register("file", "x", "x", source="magic")


@pytest.mark.parametrize("no_fts", [False, True])
def test_search_matches_title_text_and_tags_with_and_without_fts(monkeypatch, no_fts):
    if no_fts:
        monkeypatch.setenv("FRIDAY_DECK_NO_FTS", "1")
    deck.register("file", "f1", "Budget 2026", "xlsx", text="quarterly revenue forecast")
    deck.register("image", "i1", "Beach", "photo", tags=["holiday"], source="upload")
    assert [i["ref_id"] for i in deck.list_items(q="revenue")] == ["f1"]
    assert [i["ref_id"] for i in deck.list_items(q="holi")] == ["i1"]
    assert [i["ref_id"] for i in deck.list_items(q="budget 2026")] == ["f1"]
    assert deck.count_items(q="nothing-here") == 0 and deck.count_items(type="image") == 1


def test_fts_is_really_used_when_available():
    with db.read() as conn:
        assert db.has_fts(conn)


def test_provenance_chain_survives_deleting_a_parent():
    a = deck.register("image", "a", "A", source="upload")
    b = deck.register("image", "b", "B", source="upload")
    c = deck.register("image", "c", "C", source="derived", parent_ids=[a, b])
    d = deck.register("image", "d", "D", source="derived", parent_ids=[c])
    assert got(d)["parent_ids"] == [c] and got(c)["parent_ids"] == [a, b]
    assert deck.register("image", "c", "C", parent_ids=[a, "x"], source="derived") == c
    assert got(c)["parent_ids"] == [a, b, "x"]
    assert deck.delete(a) and got(c)["parent_ids"][0] == a  # provenance stays readable


def test_pin_orders_first_and_tag_filter_works():
    deck.register("note", "n1", "old")
    pinned = deck.register("note", "n2", "pinned")
    deck.register("note", "n3", "new", tags=["Work"])
    deck.update(pinned, pinned=True)
    assert deck.list_items()[0]["id"] == pinned
    assert [i["ref_id"] for i in deck.list_items(tag="work")] == ["n3"]
    assert [i["ref_id"] for i in deck.list_items(pinned=True)] == ["n2"]
    assert deck.stats()["pinned"] == 1 and deck.stats()["by_type"] == {"note": 3}


def test_delete_removes_only_the_row_unless_stored_is_requested(tmp_path):
    from app.model3d.store import ModelStore

    store = ModelStore()
    store.create("box")
    item = deck.find("model3d", "box")
    assert item and deck.delete(item["id"]) is True
    assert deck.find("model3d", "box") is None and store.exists("box")  # the registry row went, the model stays
    deck.register("model3d", "box", "box")
    assert deck.delete(deck.item_id("model3d", "box"), delete_stored=True) and not store.exists("box")
    assert deck.delete("dnope") is False


def test_model_store_registers_and_forgets_models():
    from app.model3d.store import ModelStore

    store = ModelStore()
    store.create("gear")
    assert deck.find("model3d", "gear")
    store.delete("gear")
    assert deck.find("model3d", "gear") is None


def test_schema_version_table_and_newer_database_refused(tmp_path):
    deck.count_items()
    with sqlite3.connect(db.db_path()) as conn:
        assert conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == db.SCHEMA_VERSION
        conn.execute("INSERT INTO schema_version (version) VALUES (99)")
    db._ready.discard(str(db.db_path()))
    with pytest.raises(RuntimeError, match="schema version 99"):
        deck.count_items()
    db._ready.discard(str(db.db_path()))


def test_concurrent_writes_from_threads_lose_nothing():
    errors: list[Exception] = []

    def work(n: int) -> None:
        try:
            for i in range(15):
                deck.register("note", f"t{n}-{i}", f"note {n} {i}", text="shared words")
                deck.update(deck.item_id("note", f"t{n}-{i}"), tags=[f"w{n}"])
        except Exception as e:  # pragma: no cover - reported below
            errors.append(e)

    threads = [threading.Thread(target=work, args=(n,)) for n in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    assert not errors and deck.count_items() == 90 and deck.count_items(q="shared") == 90


def test_memory_searches_keep_at_most_fifty():
    from app.deck import hooks

    for n in range(55):
        hooks.memory_search_done(f"query {n}", None, {"nodes": [], "summary": "s"})
    assert deck.count_items(type="memory_graph") == 50


def test_imaging_registers_derived_images_with_the_originals_as_parents():
    from app.imaging.edit import save_derived
    from app.vision import images, store
    from tests.vision_helpers import png_bytes

    raw = png_bytes()
    orig = store.save(raw, "orig.png", images.inspect_image(raw, "image/png"))
    meta = save_derived(
        png_bytes((50, 50)),
        "image/png",
        "edited-enhance",
        {"derived_from": [orig["id"]], "instruction": "brighter", "operation": "enhance", "model": "m"},
    )
    item = deck.find("image", meta["id"])
    assert item and item["source"] == "derived" and item["parent_ids"] == [deck.item_id("image", orig["id"])]
    assert item["subtitle"] == "brighter" and got(item["parent_ids"][0])["source"] == "upload"


def test_list_items_survives_garbage_limit_and_offset():
    for limit, offset in (("abc", 0), (None, 0), (10, "x"), (float("nan"), 0), ([1], 0), (True, 0), (10**9, -5)):
        assert isinstance(deck.list_items(None, None, None, None, limit, offset), list)  # type: ignore[arg-type]
