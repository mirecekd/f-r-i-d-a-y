# backend/tests/test_tools_friday.py
import asyncio
import json

import pytest

from app.scene import SceneStore
from app.scene_schema import KIND_PROPS, OP_FIELDS
from app.tools_friday import Ctx, register_all
from app.tools_friday.views import VIEW_DATA_SHAPES
from app.views import VIEW_KINDS
from app.voice.tools import ToolRegistry


class FakeCtx(Ctx):
    def __init__(self) -> None:
        self.sent: list[dict] = []
        super().__init__(SceneStore(), self._emit)

    async def _emit(self, msg: dict) -> None:
        self.sent.append(msg)


@pytest.fixture
def env():
    ctx = FakeCtx()
    registry = ToolRegistry()
    register_all(registry, ctx)

    def call(name: str, **args):
        return asyncio.run(registry.tools[name].handler(args))

    return ctx, registry, call


def box(i: str = "a") -> dict:
    return {"op": "add", "obj": {"id": i, "kind": "box", "pos": [0, 1, 0]}}


def test_registers_expected_tools(env):
    _, registry, _ = env
    assert set(registry.tools) == {
        "scene_apply", "scene_get", "scene_clear", "scene_camera", "scene_explode",
        "show_view", "close_view", "selected_objects",
    }
    for t in registry.tools.values():
        assert t.parameters["type"] == "object"
        json.dumps(t.parameters)


def test_scene_apply_adds_and_emits(env):
    ctx, _, call = env
    assert call("scene_apply", ops=[box("a"), box("b")]) == {"ok": True, "objects": 2}
    assert [o["id"] for o in ctx.scene.objects()] == ["a", "b"]
    assert ctx.sent == [{"t": "scene", "ops": [box("a"), box("b")]}]


def test_scene_apply_bad_op_errors_and_keeps_scene(env):
    ctx, _, call = env
    call("scene_apply", ops=[box("a")])
    ctx.sent.clear()
    result = call("scene_apply", ops=[box("b"), {"op": "add", "obj": {"id": "c", "kind": "box", "pos": [1, 2]}}])
    assert "op #1" in result["error"] and "pos" in result["error"]
    assert [o["id"] for o in ctx.scene.objects()] == ["a"]
    assert ctx.sent == []


@pytest.mark.parametrize("ops", [None, [], "x", [{"op": "teleport"}]])
def test_scene_apply_malformed_ops(env, ops):
    ctx, _, call = env
    assert "error" in call("scene_apply", ops=ops)
    assert ctx.scene.objects() == [] and ctx.sent == []


def test_scene_get_describes_with_selection(env):
    ctx, _, call = env
    call("scene_apply", ops=[box("a")])
    ctx.scene.select(["a"])
    text = call("scene_get")["scene"]
    assert "selected: a" in text and "*a box" in text


def test_selected_objects(env):
    ctx, _, call = env
    call("scene_apply", ops=[box("a"), box("b")])
    ctx.scene.select(["b"])
    result = call("selected_objects")
    assert result["ids"] == ["b"] and result["objects"][0]["id"] == "b"
    ctx.scene.select([])
    assert call("selected_objects") == {"ids": [], "objects": []}


def test_scene_clear(env):
    ctx, _, call = env
    call("scene_apply", ops=[box("a")])
    assert call("scene_clear") == {"ok": True, "objects": 0}
    assert ctx.scene.objects() == []
    assert ctx.sent[-1] == {"t": "scene", "ops": [{"op": "clear"}]}


def test_scene_camera(env):
    ctx, _, call = env
    assert call("scene_camera", pos=[0, 5, 8], look=[0, 1, 0])["ok"]
    assert ctx.scene.camera == {"pos": [0, 5, 8], "look": [0, 1, 0]}
    assert ctx.sent[-1] == {"t": "scene", "ops": [{"op": "camera", "pos": [0, 5, 8], "look": [0, 1, 0]}]}
    assert call("scene_camera", pos=[1, 1, 1])["ok"]
    assert ctx.scene.camera["look"] == [0, 0, 0]


def test_scene_camera_bad_pos(env):
    ctx, _, call = env
    assert "pos" in call("scene_camera", pos=[1, 2])["error"]
    assert "pos" in call("scene_camera")["error"]
    assert ctx.scene.camera is None and ctx.sent == []


def test_scene_explode(env):
    ctx, _, call = env
    assert call("scene_explode", factor=1.5)["ok"]
    assert ctx.scene.explode == 1.5
    assert "factor" in call("scene_explode", factor="big")["error"]
    assert ctx.scene.explode == 1.5


def test_show_view_emits_and_returns_id(env):
    ctx, _, call = env
    result = call("show_view", kind="markdown", data={"text": "# hi"}, title="T", id="v1")
    assert result == {"ok": True, "id": "v1"}
    assert ctx.sent == [{"t": "view", "id": "v1", "kind": "markdown", "data": {"text": "# hi"}, "title": "T"}]
    assert len(call("show_view", kind="json", data={"value": 1})["id"]) == 8


def test_show_view_errors(env):
    ctx, _, call = env
    assert "unknown view kind" in call("show_view", kind="video", data={})["error"]
    assert "data" in call("show_view", kind="table", data="x")["error"]
    assert ctx.sent == []


def test_close_view(env):
    ctx, _, call = env
    assert call("close_view", id="v1") == {"ok": True}
    assert ctx.sent == [{"t": "view_close", "id": "v1"}]
    assert "id" in call("close_view")["error"]


def test_descriptions_are_generated_from_constants(env):
    _, registry, _ = env
    desc = registry.tools["scene_apply"].description
    assert all(kind in desc for kind in KIND_PROPS)
    assert all(op in desc for op in OP_FIELDS)
    assert set(VIEW_DATA_SHAPES) == VIEW_KINDS
    view_desc = registry.tools["show_view"].description
    assert all(kind in view_desc for kind in VIEW_KINDS)


def test_two_connections_do_not_share_emit():
    a, b = FakeCtx(), FakeCtx()
    ra, rb = ToolRegistry(), ToolRegistry()
    register_all(ra, a)
    register_all(rb, b)
    asyncio.run(ra.tools["close_view"].handler({"id": "x"}))
    assert a.sent and not b.sent
