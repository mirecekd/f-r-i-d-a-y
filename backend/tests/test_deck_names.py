# backend/tests/test_deck_names.py
"""deck_find fuzzy matching and file/image names accepted as ids by the read/analyze tools."""

import asyncio

import pytest

from app import deck
from app.deck import names
from app.files import store as file_store
from app.files import tools as file_tools
from app.files.extract import extract
from app.scene import SceneStore
from app.tools_friday.ctx import Ctx
from app.vision import images
from app.vision import store as image_store
from app.vision.service import VisionService
from app.voice.tools import ToolRegistry
from tests.vision_helpers import png_bytes


def put_image(name: str) -> dict:
    raw = png_bytes()
    return image_store.save(raw, name, images.inspect_image(raw, "image/png"))


def put_file(name: str, text: str = "hello") -> dict:
    raw = text.encode()
    return file_store.save(raw, name, extract(raw, name))


@pytest.mark.parametrize(
    "query,expected",
    [
        ("architect", "architect.webp"),
        ("ARCHITECT.WEBP", "architect.webp"),
        ("architect.png", "architect.webp"),
        ("Architekt", "architect.webp"),
        ("plan domu", "Plán domu.png"),
        ("plan", "Plán domu.png"),
        ("DOMU", "Plán domu.png"),
    ],
)
def test_find_by_name_is_case_accent_and_extension_insensitive(query, expected):
    deck.register("image", "w1", "architect.webp", source="upload", meta={"name": "architect.webp"})
    deck.register("image", "p1", "Plán domu.png", source="upload", meta={"name": "Plán domu.png"})
    deck.register("file", "z1", "report.pdf", source="upload", meta={"name": "report.pdf"})
    hits = names.find_by_name(query)
    assert hits and hits[0]["title"] == expected


def test_find_orders_exact_before_fuzzy_and_drops_noise():
    deck.register("file", "a", "notes.txt", meta={"name": "notes.txt"})
    deck.register("file", "b", "notes-old-2020.txt", meta={"name": "notes-old-2020.txt"})
    deck.register("file", "c", "zebra.csv", meta={"name": "zebra.csv"})
    hits = names.find_by_name("notes")
    assert [h["ref_id"] for h in hits] == ["a", "b"] and hits[0]["score"] > hits[1]["score"]
    assert names.find_by_name("qqqqqqqq") == [] and names.find_by_name("   ") == []
    assert [h["ref_id"] for h in names.find_by_name("notes", ["image"])] == []


def test_find_rejects_unknown_type():
    with pytest.raises(deck.DeckError):
        names.find_by_name("x", ["movie"])


def test_resolve_name_unique_ambiguous_and_missing():
    deck.register("file", "f1", "plan-a.txt", meta={"name": "plan-a.txt"})
    deck.register("file", "f2", "plan-b.txt", meta={"name": "plan-b.txt"})
    deck.register("file", "f3", "budget.csv", meta={"name": "budget.csv"})
    assert names.resolve_name("budget", "file") == ("f3", None)
    ref, error = names.resolve_name("plan", "file")
    assert ref is None and error and "plan-a.txt" in error and "plan-b.txt" in error
    assert names.resolve_name("nothing at all", "file") == (None, None)
    assert names.resolve_name(None, "file") == (None, None)


def test_backfill_registers_items_stored_before_the_deck_existed():
    from app.deck import backfill, db

    meta = put_image("old.png")
    deck.delete(deck.item_id("image", meta["id"]))
    backfill._done.discard(str(db.db_path()))
    assert [h["ref_id"] for h in names.find_by_name("old")] == [meta["id"]]


def test_file_and_image_tools_accept_a_name(monkeypatch):
    fmeta = put_file("architect.txt", "the brief")
    imeta = put_image("sketch.png")
    sent: list = []

    async def emit(m):
        sent.append(m)

    ctx = Ctx(SceneStore(), emit)
    reg = ToolRegistry()
    file_tools.register_file_tools(reg, ctx, VisionService(ctx, lambda: "m"), lambda: "m")
    got = asyncio.run(reg.tools["read_file"].handler({"file_id": "architect"}))
    assert got["file_id"] == fmeta["id"] and "the brief" in got["content"]
    assert "unknown file_id" in asyncio.run(reg.tools["read_file"].handler({"file_id": "nonexistent"}))["error"]
    put_file("architect-2.txt")
    ambiguous = asyncio.run(reg.tools["read_file"].handler({"file_id": "arch"}))
    assert "matches several" in ambiguous["error"] and "architect-2.txt" in ambiguous["error"]
    assert asyncio.run(reg.tools["read_file"].handler({"file_id": "architect.txt"}))["file_id"] == fmeta["id"]

    from app.vision import tools as vision_tools

    imeta["analysis"] = {"summary": "a sketch"}  # cached: no model call
    image_store.write_meta(imeta)
    vreg = ToolRegistry()
    vision_tools.register_vision_tools(vreg, ctx, lambda: "m")
    seen = asyncio.run(vreg.tools["analyze_image"].handler({"image_id": "SKETCH.jpg"}))
    assert seen["image_id"] == imeta["id"] and seen["analysis"]["summary"] == "a sketch"
    assert "deck_find" in asyncio.run(vreg.tools["analyze_image"].handler({"image_id": "nope"}))["error"]
