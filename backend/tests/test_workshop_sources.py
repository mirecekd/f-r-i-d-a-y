# backend/tests/test_workshop_sources.py
"""Workshop sources: add/remove/cap/unknown ids, idempotent tile placement, enter message, forgotten items, two workshops."""

import asyncio
import json
import math

import pytest

from app import deck
from app.scene import SceneStore
from app.scene_schema import check_op
from app.tools_friday.ctx import Ctx
from app.voice.tools import ToolRegistry
from app.workshop import sources, store
from app.workshop.session import WorkshopSession
from app.workshop.tools import register_workshop_tools


def run(coro):
    return asyncio.run(coro)


def make():
    sent: list[dict] = []

    async def emit(msg):
        sent.append(msg)

    return WorkshopSession(Ctx(SceneStore(), emit)), sent


def item(name: str, text: str = "") -> str:
    return deck.register("memory_graph", f"src-{name}", name, "sub", text=text, source="upload")


def tiles(session, rec) -> list[dict]:
    return [o for o in session.ctx.scene.objects() if o["kind"] == "entity" and o["id"] in {
        d["entity_id"] for d in sources.describe(rec)}]


def test_add_remove_dedupe_and_prefix():
    rec = store.create("S")
    a, b = item("a"), item("b")
    assert sources.add(rec, [a, a, b[:8]]) == [a, b]
    assert sources.remove(rec, [a]) == [b]
    assert sources.remove(rec, ["dnothing"]) == [b]


def test_unknown_id_is_named_and_changes_nothing():
    rec = store.create("S")
    a = item("a")
    with pytest.raises(store.WorkshopError, match="zzz-missing"):
        sources.add(rec, [a, "zzz-missing"])
    assert rec["sources"] == []
    with pytest.raises(store.WorkshopError, match="list of deck ids"):
        sources.add(rec, "d1")


def test_cap_is_twelve():
    rec = store.create("S")
    ids = [item(f"i{n}") for n in range(13)]
    sources.add(rec, ids[:12])
    with pytest.raises(store.WorkshopError, match="at most 12"):
        sources.add(rec, ids[12:])
    assert len(rec["sources"]) == 12


def test_describe_truncates_the_stored_text():
    rec = store.create("S")
    sources.add(rec, [item("long", "x" * 2000)])
    (entry,) = sources.describe(rec)
    assert len(entry["summary"]) == sources.SUMMARY_CHARS
    assert entry["kind"] == "memory_graph" and entry["entity_id"].startswith("ent-memory-")


def test_old_records_without_sources_load_empty():
    rec = store.create("S")
    path = store.workshops_dir() / f"{rec['id']}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw["sources"]
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert store.load(rec["id"])["sources"] == []


def test_enter_carries_sources_and_tiles_ring_the_table():
    async def go():
        s, sent = make()
        rec = store.create("S")
        sources.add(rec, [item("a"), item("b"), item("c")])
        store.save(rec)
        await s.open(rec["id"])
        return s, sent, rec

    s, sent, rec = run(go())
    enter = next(m for m in sent if m.get("op") == "enter")
    assert [x["title"] for x in enter["sources"]] == ["a", "b", "c"]
    assert all(x["entity_id"].startswith("ent-memory-") for x in enter["sources"])
    origin = store.origin_of(rec["origin_n"])
    placed = tiles(s, rec)
    assert len(placed) == 3
    for o in placed:
        assert math.hypot(o["pos"][0] - origin[0], o["pos"][2] - origin[2]) > 3.0
    for m in sent:
        if m.get("t") == "scene":
            for op in m["ops"]:
                check_op(op)


def test_placement_is_idempotent():
    async def go():
        s, sent = make()
        rec = store.create("S")
        sources.add(rec, [item("a"), item("b")])
        store.save(rec)
        await s.open(rec["id"])
        before = sorted((o["id"], tuple(o["pos"])) for o in tiles(s, rec))
        count = len(sent)
        await sources.place(s.ctx, rec)
        await sources.place(s.ctx, rec)
        return before, sorted((o["id"], tuple(o["pos"])) for o in tiles(s, rec)), len(sent) - count

    before, after, extra = run(go())
    assert before == after and extra == 0


def test_tool_adds_and_removes_tiles_from_the_scene():
    async def go():
        s, _ = make()
        reg = ToolRegistry()
        session = register_workshop_tools(reg, s.ctx)
        await session.open(None, "T")
        a, b = item("a", "alpha text"), item("b")
        tool = reg.tools["workshop_sources"]
        added = await tool.handler({"add": [a, b]})
        placed = {o["title"] for o in s.ctx.scene.objects() if o["id"].startswith("ent-memory-")}
        removed = await tool.handler({"remove": [a]})
        left = {o["title"] for o in s.ctx.scene.objects() if o["id"].startswith("ent-memory-")}
        bad = await tool.handler({"add": ["zzz-missing"]})
        return added, placed, removed, left, bad

    added, placed, removed, left, bad = run(go())
    assert [d["title"] for d in added["sources"]] == ["a", "b"] and "alpha text" in added["sources"][0]["summary"]
    assert placed == {"a", "b"} and left == {"b"}
    assert [d["title"] for d in removed["sources"]] == ["b"]
    assert "zzz-missing" in bad["error"]


def test_forgotten_source_is_dropped_with_a_note():
    async def go():
        s, sent = make()
        rec = store.create("S")
        a, b = item("a"), item("b")
        sources.add(rec, [a, b])
        store.save(rec)
        await s.open(rec["id"])
        deck.delete(a)
        await s.leave()
        sent.clear()
        await s.open(rec["id"])
        return s, sent, rec, a, b

    s, sent, rec, a, b = run(go())
    enter = next(m for m in sent if m.get("op") == "enter")
    assert [x["title"] for x in enter["sources"]] == ["b"]
    assert any(a in n for n in enter["notes"])
    assert store.load(rec["id"])["sources"] == [b]
    assert [o["title"] for o in s.ctx.scene.objects() if o["id"].startswith("ent-memory-")] == ["b"]


def test_two_workshops_keep_their_own_sources():
    async def go():
        s, _ = make()
        one, two = store.create("One"), store.create("Two")
        a, b = item("a"), item("b")
        sources.add(one, [a])
        sources.add(two, [b])
        store.save(one)
        store.save(two)
        await s.open(one["id"])
        await s.open(two["id"])
        return s, one, two

    s, one, two = run(go())
    assert [d["title"] for d in sources.describe(one)] == ["a"]
    assert [d["title"] for d in sources.describe(two)] == ["b"]
    by_title = {o["title"]: o for o in s.ctx.scene.objects() if o["id"].startswith("ent-memory-")}
    assert set(by_title) == {"a", "b"}
    assert abs(by_title["a"]["pos"][2] - 400.0) < 12 and abs(by_title["b"]["pos"][2] - 800.0) < 12
