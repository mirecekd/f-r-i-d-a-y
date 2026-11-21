# backend/tests/test_model3d_tools.py
import asyncio
import functools

import pytest

from app.model3d.packs import register_pack
from app.model3d.store import ModelStore
from app.model3d.tools import register_model_tools
from app.scene import SceneStore
from app.tools_friday import Ctx
from app.voice.tools import ToolRegistry

EXPECTED = {
    "model_create", "model_add_part", "model_edit_part", "model_remove_part", "model_group", "model_layer_set",
    "model_explode", "model_get", "model_measure", "model_annotate", "model_undo", "model_redo", "model_snapshot",
    "model_restore", "model_list", "model_clear", "model_propose", "model_accept", "model_reject", "pack_list", "pack_generate",
}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FRIDAY_DATA_DIR", str(tmp_path))
    sent: list[dict] = []

    async def emit(msg):
        sent.append(msg)

    ctx = Ctx(SceneStore(), emit)
    reg = ToolRegistry()
    register_model_tools(reg, ctx)
    return reg, ctx, sent


async def call(reg, name, /, **args):
    return await reg.tools[name].handler(args)


def sync(fn):
    @functools.wraps(fn)
    def run(env):
        return asyncio.run(fn(env))
    return run


def test_tool_list_and_schemas(env):
    reg = env[0]
    assert set(reg.tools) == EXPECTED
    assert all(t.parameters["type"] == "object" for t in reg.tools.values())
    assert reg.tools["model_clear"].risky and reg.tools["model_clear"].confirm_summary({"model": "x"})


@sync
async def test_build_edit_undo_flow(env):
    reg, ctx, sent = env
    assert (await call(reg, "model_create", id="enc"))["ok"]
    r = await call(reg, "model_add_part", part={"id": "shell", "kind": "box", "scale": [40, 20, 30], "layer": "body", "props": {"mat": "PLA"}})
    assert r["ok"]
    await call(reg, "model_add_part", part={"id": "lid", "kind": "box", "layer": "lid", "pos": [0, 20, 0]})
    assert "m:enc:shell" in {o["id"] for o in ctx.scene.objects()}
    assert sent and sent[-1]["t"] == "scene"
    text = (await call(reg, "model_get"))["model"]
    assert "shell box" in text and '"mat":"PLA"' in text
    assert (await call(reg, "model_measure", a="shell", b="lid"))["distance"] == 20
    assert (await call(reg, "model_edit_part", id="lid", props={"color": "#f00"}))["ok"]
    await call(reg, "model_layer_set", layer="lid", visible=False)
    assert "m:enc:lid" not in {o["id"] for o in ctx.scene.objects()}
    assert (await call(reg, "model_undo"))["ok"]
    assert "m:enc:lid" in {o["id"] for o in ctx.scene.objects()}
    assert (await call(reg, "model_redo"))["ok"]
    assert "m:enc:lid" not in {o["id"] for o in ctx.scene.objects()}


@sync
async def test_errors_and_group_annotate_remove(env):
    reg, ctx, _ = env
    assert "error" in await call(reg, "model_add_part", part={"id": "a"})  # no model yet
    await call(reg, "model_create", id="m")
    assert "error" in await call(reg, "model_add_part", part={"id": "a", "kind": "nope"})
    assert "error" in await call(reg, "model_add_part", part={"id": "a", "parent": "zz"})
    await call(reg, "model_add_part", part={"id": "a", "kind": "box"})
    await call(reg, "model_add_part", part={"id": "b", "kind": "box"})
    assert (await call(reg, "model_group", id="g", parts=["a", "b"]))["ok"]
    assert (await call(reg, "model_annotate", part="a", text="hi"))["annotation"] == "note1"
    assert ctx.scene.objects() and "m:m:note1" in {o["id"] for o in ctx.scene.objects()}
    assert (await call(reg, "model_remove_part", id="g"))["removed"][0] == "g"
    assert "error" in await call(reg, "model_remove_part", id="g")
    assert "error" in await call(reg, "model_measure", a="x", b="y")


@sync
async def test_explode_and_snapshot(env):
    reg, ctx, sent = env
    await call(reg, "model_create", id="m")
    await call(reg, "model_add_part", part={"id": "a", "kind": "box", "layer": "l0"})
    await call(reg, "model_add_part", part={"id": "b", "kind": "box", "layer": "l1"})
    await call(reg, "model_layer_set", layer="l1", z_index=1)
    r = await call(reg, "model_explode", factor=1, spacing=10)
    assert r["moved"] == 2 and sent[-1]["ops"][0]["props"]["pos"] is not None
    assert next(o for o in ctx.scene.objects() if o["id"] == "m:m:b")["pos"] == [0, 10, 0]
    await call(reg, "model_explode", factor=0)
    assert next(o for o in ctx.scene.objects() if o["id"] == "m:m:b")["pos"] == [0, 0, 0]
    await call(reg, "model_snapshot", name="v1")
    await call(reg, "model_remove_part", id="a")
    assert (await call(reg, "model_restore", name="v1"))["parts"] == 2
    assert "error" in await call(reg, "model_explode", factor=1, by="bogus")


@sync
async def test_propose_accept_reject_and_clear(env):
    reg, ctx, _ = env
    await call(reg, "model_create", id="pcb")
    await call(reg, "model_add_part", part={"id": "t1", "kind": "polyline", "geom": {"pts": [[0, 0, 0], [5, 0, 0]]}})
    r = await call(reg, "model_propose", changes=[{"op": "edit", "id": "t1", "props": {"geom": {"pts": [[0, 0, 0], [5, 5, 0]]}}}])
    assert r["proposal"] == "p1" and "~ edit t1" in r["diff"]
    assert "ghost:p1:t1" in {o["id"] for o in ctx.scene.objects()}
    assert ModelStore().load("pcb").parts["t1"].geom["pts"][1] == [5, 0, 0]  # unchanged until accepted
    assert (await call(reg, "model_accept", proposal="p1"))["ok"]
    assert ModelStore().load("pcb").parts["t1"].geom["pts"][1] == [5, 5, 0]
    assert not [o for o in ctx.scene.objects() if o["id"].startswith("ghost:")]
    r2 = await call(reg, "model_propose", changes=[{"op": "remove", "id": "t1"}])
    assert (await call(reg, "model_reject", proposal=r2["proposal"]))["ok"]
    assert "m:pcb:t1" in {o["id"] for o in ctx.scene.objects()}
    assert "error" in await call(reg, "model_accept", proposal="p99")
    assert (await call(reg, "model_list"))["models"] == ["pcb"]
    await call(reg, "model_clear")
    assert not ctx.scene.objects() and (await call(reg, "model_list"))["models"] == []


@sync
async def test_packs(env):
    reg = env[0]
    assert "demo" not in (await call(reg, "pack_list"))["packs"]
    assert "error" in await call(reg, "pack_generate", pack="nope")
    register_pack("demo", lambda spec: [{"id": "x", "kind": "box"}])
    assert (await call(reg, "pack_generate", pack="demo", dry_run=True))["parts"][0]["id"] == "x"
    assert {"building", "demo"} <= set((await call(reg, "pack_list"))["packs"])


@sync
async def test_pack_generate_without_spec_builds_framed_model(env):
    reg, ctx, sent = env
    r = await call(reg, "pack_generate", pack="pcb")
    assert r["ok"] and r["model"] == "pcb" and r["parts"] > 5 and r["spec_used"]["size_mm"] == [60, 40]
    cams = [op for m in sent for op in m["ops"] if op["op"] == "camera"]
    assert len(cams) == 1
    assert ctx.scene.objects() and "m:pcb:board" in {o["id"] for o in ctx.scene.objects()}
    assert (await call(reg, "pack_generate", pack="pcb", frame=False, spec={"size_mm": [30, 20]}))["ok"]
    assert len([op for m in sent for op in m["ops"] if op["op"] == "camera"]) == 1
    assert (await call(reg, "pack_generate", pack="enclosure", model="case"))["ok"]
    assert (await call(reg, "pack_generate", pack="building", model="house"))["ok"]
    assert (await call(reg, "model_list"))["models"] == ["case", "house", "pcb"]
    assert "pcb" in reg.tools["pack_generate"].description and "size_mm" in reg.tools["pack_generate"].description


@sync
async def test_model_ids_are_normalised_and_create_is_not_duplicated(env):
    reg, ctx, _ = env
    assert (await call(reg, "model_create", id="PCB Model"))["model"] == "pcb_model"
    again = await call(reg, "model_create", id="pcb-model")
    assert "exists" in again["error"]
    assert (await call(reg, "model_add_part", model="PCB_Model", part={"id": "a", "kind": "box"}))["ok"]
    assert (await call(reg, "model_list"))["models"] == ["pcb_model"]
    assert (await call(reg, "model_list"))["details"][0]["parts"] == 1


@sync
async def test_frame_on_new_model_and_explode_only_and_suppressible(env):
    reg, _, sent = env

    def cameras():
        return [op for m in sent for op in m["ops"] if op["op"] == "camera"]
    await call(reg, "model_create", id="m")
    await call(reg, "model_add_part", part={"id": "a", "kind": "box", "scale": [100, 2, 60], "layer": "l0"})
    assert len(cameras()) == 1
    await call(reg, "model_add_part", part={"id": "b", "kind": "box", "scale": [10, 2, 10], "layer": "l1"})
    assert len(cameras()) == 1  # size did not change much
    await call(reg, "model_layer_set", layer="l1", z_index=1)
    await call(reg, "model_explode", factor=1, spacing=300, frame=False)
    assert len(cameras()) == 1
    await call(reg, "model_explode", factor=1, spacing=300)
    assert len(cameras()) == 2
