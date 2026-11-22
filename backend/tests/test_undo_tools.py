# backend/tests/test_undo_tools.py
"""UndoService: scene journal (add, set, del with children, clear), redo, cap, empty message, delegation to model3d, risky tools."""

import asyncio
from typing import Any

from app.model3d.tools import register_model_tools
from app.scene import SceneStore
from app.tools_friday import Ctx, register_all
from app.undo import UndoService
from app.voice.tools import Tool, ToolRegistry


def run(coro):
    return asyncio.run(coro)


class Rig:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

        async def emit(msg: dict[str, Any]) -> None:
            self.sent.append(msg)

        self.scene = SceneStore()
        self.ctx = Ctx(self.scene, emit)
        self.registry = ToolRegistry()
        register_all(self.registry, self.ctx)
        register_model_tools(self.registry, self.ctx)
        self.deleted: list[str] = []

        async def forget(args: dict[str, Any]) -> dict[str, Any]:
            self.deleted.append("x")
            self.scene.apply([{"op": "del", "id": "a"}])
            return {"ok": True}

        self.registry.register(Tool("deck_forget", "forget", {"type": "object", "properties": {}}, forget, risky=True))
        self.undo = UndoService(self.registry, self.ctx)

    def call(self, name: str, **args: Any) -> dict[str, Any]:
        return run(self.registry.tools[name].handler(args))

    def apply(self, *ops: dict[str, Any]) -> dict[str, Any]:
        return self.call("scene_apply", ops=list(ops))

    def ids(self) -> list[str]:
        return [o["id"] for o in self.scene.objects()]


def box(i: str, **kw: Any) -> dict[str, Any]:
    return {"op": "add", "obj": {"id": i, "kind": "box", **kw}}


def test_add_then_undo_removes_and_redo_restores():
    r = Rig()
    r.apply(box("wall_1", pos=[0, 0, 0]))
    out = r.call("undo")
    assert out["message"] == "Undone: added wall_1"
    assert r.ids() == []
    assert r.call("redo")["message"] == "Redone: added wall_1"
    assert r.ids() == ["wall_1"]


def test_set_then_undo_restores_props():
    r = Rig()
    r.apply(box("wall_1", pos=[0, 0, 0], color="#fff"))
    r.apply({"op": "set", "id": "wall_1", "props": {"pos": [3, 0, 0], "color": "#000"}})
    assert r.call("undo")["message"] == "Undone: moved wall_1"
    obj = r.scene.objects()[0]
    assert obj["pos"] == [0, 0, 0] and obj["color"] == "#fff"


def test_delete_then_undo_restores_children():
    r = Rig()
    r.apply(box("room"), box("door", parent="room"), box("knob", parent="door"), box("other"))
    r.apply({"op": "del", "id": "room"})
    assert r.ids() == ["other"]
    assert r.call("undo")["message"] == "Undone: removed 3 objects"
    assert sorted(r.ids()) == ["door", "knob", "other", "room"]
    assert {o["id"]: o.get("parent") for o in r.scene.objects()}["knob"] == "door"


def test_clear_undo_and_scene_message_reaches_browser():
    r = Rig()
    r.apply(box("a"), box("b"))
    r.call("scene_clear")
    r.sent.clear()
    assert r.call("undo")["message"] == "Undone: cleared the scene"
    assert sorted(r.ids()) == ["a", "b"]
    assert r.sent and r.sent[0]["t"] == "scene"


def test_camera_moves_are_not_journaled():
    r = Rig()
    r.call("scene_camera", pos=[1, 2, 3])
    assert r.call("undo") == {"error": "Nothing to undo."}


def test_new_action_clears_redo_and_steps():
    r = Rig()
    r.apply(box("a"))
    r.apply(box("b"))
    assert r.call("undo", steps=2)["steps"] == 2
    assert r.ids() == []
    r.call("redo")
    r.apply(box("c"))
    assert r.call("redo") == {"error": "Nothing to redo."}


def test_cap_30_entries():
    r = Rig()
    for i in range(35):
        r.apply(box(f"o{i}"))
    assert r.call("undo", steps=100)["steps"] == 30
    assert len(r.ids()) == 5


def test_nothing_to_undo_message():
    r = Rig()
    assert r.call("undo") == {"error": "Nothing to undo."}
    assert r.call("redo") == {"error": "Nothing to redo."}


def test_model_change_delegates_to_model3d():
    r = Rig()
    r.apply(box("a"))
    r.call("model_create", id="m1")
    r.call("model_add_part", part={"id": "p1", "kind": "box"})
    assert r.undo.last_domain == "model"
    before = r.ids()
    out = r.call("undo")
    assert out["message"] == "Undone: the last model change"
    assert len(r.ids()) < len(before)
    assert "a" in r.ids()  # the scene entry stays on the journal
    assert r.call("redo")["message"] == "Redone: the last model change"
    assert len(r.ids()) == len(before)


def test_scene_journal_first_then_model_history_when_scene_action_is_newest():
    r = Rig()
    r.call("model_create", id="m1")
    r.call("model_add_part", part={"id": "p1", "kind": "box"})
    with_part = r.ids()
    r.apply(box("a"))
    assert r.undo.last_domain == "scene"
    assert r.call("undo")["message"] == "Undone: added a"
    assert r.call("undo")["message"] == "Undone: the last model change"
    assert len(r.ids()) < len(with_part)


def test_risky_tools_are_not_journaled():
    r = Rig()
    r.apply(box("a"))
    r.call("undo")
    r.apply(box("a"))
    r.call("deck_forget")
    assert r.ids() == []
    out = r.call("undo")
    assert out["message"] == "Undone: added a"  # the journal knows only the add; forget itself is not undoable
    assert r.ids() == []
