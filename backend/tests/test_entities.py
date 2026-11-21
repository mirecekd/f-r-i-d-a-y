# backend/tests/test_entities.py
"""Entities and links: ref validation, layout, creation, entity tools with fakes, entity_open and entity_run."""

import asyncio

import pytest

from app.approval import Approvals
from app.entities import layout
from app.entities.links import link_id
from app.entities.tools import register_entity_tools
from app.files import store as file_store
from app.files.extract import extract
from app.files.service import FileService
from app.scene import SceneStore
from app.scene_schema import SceneError, check_op
from app.tools_friday.ctx import Ctx
from app.vision.service import VisionService
from app.voice.tools import Tool, ToolRegistry


def run(coro):
    return asyncio.run(coro)


def add_op(**obj) -> dict:
    return {"op": "add", "obj": {"kind": "entity", "shape": "doc", "title": "t", **obj}}


@pytest.mark.parametrize("ref", [
    {"type": "file", "id": "abc123"}, {"type": "tool", "id": "read_file"}, {"type": "image", "id": "a" * 80},
])
def test_ref_accepts_valid_values(ref):
    check_op(add_op(id="e", ref=ref))


@pytest.mark.parametrize("ref", [
    {"type": "video", "id": "x"}, {"type": "file", "id": "a" * 81}, {"type": "file", "id": "../etc"},
    {"type": "file", "id": "a/b"}, {"type": "file", "id": ""}, {"type": "file"}, "file:x", {"type": "file", "id": "x", "extra": 1},
])
def test_ref_rejects_bad_values(ref):
    with pytest.raises(SceneError):
        check_op(add_op(id="e", ref=ref))


def test_ref_is_a_common_prop_and_shown_by_describe():
    scene = SceneStore()
    scene.apply([{"op": "add", "obj": {"id": "b", "kind": "box", "ref": {"type": "model", "id": "m1"}}}])
    assert "ref=model:m1" in scene.describe()


def test_entity_and_link_props_are_validated():
    with pytest.raises(SceneError):
        check_op(add_op(id="e", shape="spaceship"))
    with pytest.raises(SceneError):
        check_op({"op": "add", "obj": {"id": "l", "kind": "link", "from": "a", "to": "b", "style": "wavy"}})
    with pytest.raises(SceneError):
        check_op({"op": "add", "obj": {"id": "l", "kind": "link", "from": 5, "to": "b"}})
    check_op({"op": "add", "obj": {"id": "l", "kind": "link", "from": "a", "to": "b", "style": "dashed", "label": "x"}})
    check_op({"op": "set", "id": "e", "props": {"thumb": "/api/uploads/x.png", "title": "new"}})


def test_layout_is_deterministic_and_never_overlaps():
    taken: list[list[float]] = []
    for _ in range(40):
        slot = layout.next_free_slot(taken)
        assert all(((slot[0] - t[0]) ** 2 + (slot[2] - t[2]) ** 2) ** 0.5 >= layout.SPACING - 1e-6 for t in taken)
        taken.append(slot)
    again: list[list[float]] = []
    for _ in range(40):
        again.append(layout.next_free_slot(again))
    assert again == taken


def test_layout_avoids_an_existing_object_on_the_first_slot():
    first = layout.next_free_slot([])
    assert layout.next_free_slot([first]) != first
    assert layout.next_free_slot([[first[0] + 1, first[1], first[2]]]) != first


@pytest.mark.parametrize("mode", ["arc", "grid", "around"])
def test_arrange_gives_spaced_positions(mode):
    spots = layout.arrange(9, mode, [0, 1.2, 0])
    assert len(spots) == 9
    for i, a in enumerate(spots):
        for b in spots[i + 1:]:
            assert ((a[0] - b[0]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5 >= layout.SPACING - 0.05


class Harness:
    def __init__(self):
        self.sent: list[dict] = []
        self.asked: list[tuple] = []
        self.allow = True
        ctx = Ctx(SceneStore(), self.emit)
        self.ctx = ctx
        self.registry = ToolRegistry()
        vision = VisionService(ctx, lambda: "m")
        files = FileService(ctx, vision)
        self.vision, self.files = vision, files
        approvals = Approvals(self.emit)

        async def ask(tool, summary, args, timeout=0):
            self.asked.append((tool, args))
            return self.allow

        approvals.ask = ask  # type: ignore[method-assign]
        self.calls: list[dict] = []

        async def ref_tool(args):
            self.calls.append(args)
            return {"ok": True}

        for name, risky in (("safe_ref", False), ("risky_ref", True)):
            self.registry.register(Tool(name, "d", {"type": "object", "properties": {"ref": {"type": "object"}}}, ref_tool, risky=risky))
        self.registry.register(Tool("no_ref", "d", {"type": "object", "properties": {}}, ref_tool))
        register_entity_tools(self.registry, ctx, vision, files, approvals)

    async def emit(self, m):
        self.sent.append(m)

    def call(self, name, **args):
        return run(self.registry.tools[name].handler(args))

    def add(self, *objs):
        self.ctx.scene.apply([{"op": "add", "obj": o} for o in objs])


def tile(oid, ref, **kw):
    obj = {"id": oid, "kind": "entity", "shape": "doc", "title": oid, "pos": [0, 1, 0], **kw}
    return {**obj, "ref": ref} if ref else obj


def test_link_list_unlink_roundtrip():
    h = Harness()
    h.add(tile("a", {"type": "file", "id": "f1"}), tile("b", {"type": "tool", "id": "safe_ref"}))
    res = h.call("entity_link", from_id="a", to_id="b", label="in")
    assert res == {"ok": True, "link_id": link_id("a", "b")}
    assert h.sent[-1]["ops"][0]["obj"]["kind"] == "link"
    assert "links[" in h.call("entity_list")["entities"] and "ref=file:f1" in h.call("entity_list")["entities"]
    assert "error" in h.call("entity_link", from_id="a", to_id="zz")
    assert "error" in h.call("entity_link", from_id="a", to_id="a")
    assert h.call("entity_unlink", link_id=res["link_id"]) == {"ok": True}
    assert "links[" not in h.call("entity_list")["entities"]
    assert "error" in h.call("entity_unlink", link_id="nope")


def test_deleting_an_entity_never_touches_the_stored_file(tmp_path):
    raw = b"hello"
    meta = file_store.save(raw, "a.txt", extract(raw, "a.txt"))
    h = Harness()
    h.add(tile("ent-file-x", {"type": "file", "id": meta["id"]}))
    h.ctx.scene.apply([{"op": "del", "id": "ent-file-x"}])
    assert file_store.resolve(meta["id"]) is not None


def test_arrange_tweens_with_set_ops():
    h = Harness()
    h.add(tile("a", None, pos=[0, 1, 0]), tile("b", None, pos=[0, 1, 0]), tile("c", None, pos=[0, 1, 0]))
    assert h.call("entity_arrange", layout="grid") == {"ok": True, "moved": 3}
    ops = h.sent[-1]["ops"]
    assert all(o["op"] == "set" and o["ms"] > 0 and len(o["props"]["pos"]) == 3 for o in ops)
    assert "error" in h.call("entity_arrange", layout="around")
    assert h.call("entity_arrange", layout="around", center_id="a")["moved"] == 2
    assert "error" in h.call("entity_arrange", layout="spiral")


def test_entity_open_emits_the_file_card_and_rejects_unknown(tmp_path):
    raw = b"col\n1\n"
    meta = file_store.save(raw, "t.csv", extract(raw, "t.csv"))
    h = Harness()
    h.add(tile("ent-file-1", {"type": "file", "id": meta["id"]}), tile("n", None))
    assert h.call("entity_open", id="ent-file-1")["ok"]
    assert h.sent[-1]["t"] == "view" and h.sent[-1]["kind"] == "file_card" and h.sent[-1]["title"] == "t.csv"
    assert "error" in h.call("entity_open", id="nope")
    assert "no stored item" in h.call("entity_open", id="n")["error"]


def test_entity_messages_open_link_remove_and_report_errors(tmp_path):
    from app.entities.messages import handle_entity_message

    raw = b"col\n1\n"
    meta = file_store.save(raw, "t.csv", extract(raw, "t.csv"))
    h = Harness()
    h.add(tile("a", {"type": "file", "id": meta["id"]}), tile("b", None))
    out: list[dict] = []

    async def emit(m):
        out.append(m)

    agent = type("A", (), {"vision": h.vision, "files": h.files})()

    def send(**m):
        run(handle_entity_message(emit, agent, m))

    send(t="entity_open", id="zz")
    assert out[-1]["t"] == "error" and "entity_open" in out[-1]["message"]
    send(t="entity_link", **{"from": "a", "to": "b"})
    assert out[-1]["ops"][0]["obj"]["kind"] == "link" and len([o for o in h.ctx.scene.objects() if o["kind"] == "link"]) == 1
    send(t="entity_remove", id="a")
    assert [o["id"] for o in h.ctx.scene.objects()] == ["b"] and file_store.resolve(meta["id"]) is not None
    send(t="entity_remove", id="a")
    assert out[-1]["t"] == "error"


def test_entity_run_uses_the_normal_tool_path_and_approval():
    h = Harness()
    h.add(tile("f", {"type": "file", "id": "f1"}), tile("i", {"type": "image", "id": "i1"}),
          tile("t1", {"type": "tool", "id": "safe_ref"}), tile("t2", {"type": "tool", "id": "risky_ref"}),
          tile("t3", {"type": "tool", "id": "no_ref"}))
    for tid in ("t1", "t2", "t3"):
        h.call("entity_link", from_id="f", to_id=tid)
    h.call("entity_link", from_id="i", to_id="t1")
    res = h.call("entity_run", tool_entity_id="t1")
    assert res["ok"] and [c["ref"]["id"] for c in h.calls] == ["f1", "i1"] and not h.asked
    h.calls.clear()
    res = h.call("entity_run", tool_entity_id="t2")
    assert res["ok"] and h.asked == [("risky_ref", {"ref": {"type": "file", "id": "f1"}})] and len(h.calls) == 1
    h.calls.clear()
    h.allow = False
    assert h.call("entity_run", tool_entity_id="t2")["results"][0]["error"] == "denied by user" and not h.calls
    err = h.call("entity_run", tool_entity_id="t3")["error"]
    assert "no ref input" in err and "safe_ref" in err and "risky_ref" in err
    assert "error" in h.call("entity_run", tool_entity_id="f")
    h.add(tile("lonely", {"type": "tool", "id": "safe_ref"}))
    assert "link at least one" in h.call("entity_run", tool_entity_id="lonely")["error"]


def test_file_and_image_tools_accept_a_ref(tmp_path):
    from app.files import tools as file_tools

    raw = b"some text"
    meta = file_store.save(raw, "a.txt", extract(raw, "a.txt"))
    h = Harness()
    reg = ToolRegistry()
    file_tools.register_file_tools(reg, h.ctx, h.vision, lambda: "m")
    out = run(reg.tools["read_file"].handler({"ref": {"type": "file", "id": meta["id"]}}))
    assert out["ok"] and out["file_id"] == meta["id"]
    assert "error" in run(reg.tools["read_file"].handler({"ref": {"type": "image", "id": meta["id"]}}))


def test_file_to_scene_places_distinct_entities_and_opens_no_card(tmp_path):
    h = Harness()
    metas = [file_store.save(f"x{i}".encode(), f"f{i}.txt", extract(f"x{i}".encode(), f"f{i}.txt")) for i in range(3)]
    for m in metas:
        assert run(h.files.show_entity(m))["ok"]
    ents = [o for o in h.ctx.scene.objects() if o["kind"] == "entity"]
    assert len(ents) == 3 and all(o["id"].startswith("ent-file-") for o in ents)
    assert not [m for m in h.sent if m["t"] == "view"]
    assert len({tuple(o["pos"]) for o in ents}) == 3


def test_workshop_shape_and_ref_are_accepted():
    check_op(add_op(id="e", shape="workshop", ref={"type": "workshop", "id": "w1"}))
    with pytest.raises(SceneError):
        check_op(add_op(id="e", shape="forge"))
