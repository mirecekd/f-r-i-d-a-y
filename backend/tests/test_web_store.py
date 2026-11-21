# backend/tests/test_web_store.py
"""Snapshot store: idempotent by normalised URL, fetch count, deck registration, entity placement and card."""

import asyncio
import json

import pytest
from web_fixtures import article_extract

from app.deck import query, registry
from app.deck.items import item_id
from app.deck.place import entity_spec
from app.scene_entity_schema import check_ref
from app.scene_errors import SceneError
from app.webpages import card, store
from app.webpages.urlguard import UrlRefused

URL = "https://Example.org:443/solder?utm_source=x#top"


def test_save_writes_snapshot_and_registers_deck_item():
    meta = store.save(URL, 1234, "text/html", article_extract())
    assert meta["url"] == "https://example.org/solder" and meta["fetch_count"] == 1 and meta["title"] == "Soldering basics"
    folder = store.web_dir() / meta["id"]
    assert sorted(p.name for p in folder.iterdir()) == ["meta.json", "text.txt"]
    assert "flux" in (folder / "text.txt").read_text()
    assert json.loads((folder / "meta.json").read_text())["id"] == meta["id"]
    item = query.get(item_id("web", meta["id"]))
    assert item and item["type"] == "web" and item["subtitle"] == "example.org" and item["meta"]["url"] == meta["url"]
    assert query.list_items(None, "flux", None, None, 10, 0)[0]["id"] == item["id"]  # full text search finds the excerpt


def test_same_normalised_url_refreshes_the_same_snapshot_and_counts_fetches():
    first = store.save(URL, 10, "text/html", article_extract())
    second = store.save("https://example.org/solder?utm_medium=y", 20, "text/html", article_extract())
    assert second["id"] == first["id"] and second["fetch_count"] == 2
    assert second["first_fetched_at"] == first["first_fetched_at"]
    assert len(store.list_pages()) == 1 and query.count_items("web", None) == 1


def test_user_rename_survives_a_refresh():
    meta = store.save(URL, 10, "text/html", article_extract())
    registry.update(item_id("web", meta["id"]), title="My iron notes")
    store.save(URL, 10, "text/html", article_extract())
    item = query.get(item_id("web", meta["id"]))
    assert item is not None and item["title"] == "My iron notes"


def test_refused_url_is_not_stored():
    with pytest.raises(UrlRefused):
        store.save("http://127.0.0.1/", 1, "text/html", article_extract())
    assert store.list_pages() == []


def test_resolve_by_prefix_and_rejects_path_tricks():
    meta = store.save(URL, 10, "text/html", article_extract())
    found = store.resolve(meta["id"][:8])
    assert found is not None and found["id"] == meta["id"]
    assert store.load("../../etc") is None and store.resolve("../x") is None and store.text_of("../x") == ""
    assert store.delete("../x") is False


def test_entity_spec_and_ref_type_for_web_items():
    meta = store.save(URL, 10, "text/html", article_extract())
    item = query.get(item_id("web", meta["id"]))
    assert item is not None
    spec = entity_spec(item)
    assert spec["ref_type"] == "web" and spec["shape"] == "doc" and spec["subtitle"] == "example.org"
    check_ref({"type": "web", "id": meta["id"]})
    with pytest.raises(SceneError):
        check_ref({"type": "webx", "id": meta["id"]})


def test_card_data_has_source_link_and_untrusted_text_only_as_data():
    meta = store.save(URL, 10, "text/html", article_extract())
    data = card.card_data(meta, store.text_of(meta["id"]))
    assert data["source_url"] == "https://example.org/solder" and data["kind"] == "web" and data["title"] == "Soldering basics"
    assert data["outline"] and "Soldering basics" in data["text_excerpt"]


def test_open_ref_emits_file_card_for_a_web_entity():
    from app.entities.open import open_ref

    class Ctx:
        sent: list = []

        async def emit(self, msg):
            self.sent.append(msg)

    meta = store.save(URL, 10, "text/html", article_extract())
    ctx = Ctx()
    out = asyncio.run(open_ref(ctx, None, None, {"type": "web", "id": meta["id"]}))  # type: ignore[arg-type]
    assert out["ok"] and ctx.sent[0]["kind"] == "file_card" and ctx.sent[0]["data"]["source_url"] == meta["url"]
    gone = asyncio.run(open_ref(ctx, None, None, {"type": "web", "id": "0" * 32}))  # type: ignore[arg-type]
    assert "no longer exists" in gone["error"]
