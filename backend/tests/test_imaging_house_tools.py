# backend/tests/test_imaging_house_tools.py
"""house_from_sources and house_refine tools (Gemini faked): model creation, questions, proposals instead of regeneration."""

import asyncio
import json

import pytest

from app.imaging import house
from app.imaging.house_refine import changes_from
from app.imaging.tools_house import register_house_tools
from app.model3d.tools import register_model_tools
from app.voice.tools import ToolRegistry
from tests.imaging_helpers import FakeCtx, stored_image
from tests.test_imaging_house import RAW


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def tools(monkeypatch):
    ctx = FakeCtx()
    reg = ToolRegistry()
    models = register_model_tools(reg, ctx)
    register_house_tools(reg, models, lambda: "gemini-flash-latest")
    return reg, models, ctx


def fake_ask(monkeypatch, payload):
    async def fake_chat(model, messages, tools):
        return {"text": json.dumps(payload), "tool_calls": []}

    monkeypatch.setattr(house, "chat_gemini", fake_chat)

    async def pick(pinned):
        return "gemini-flash-latest"

    monkeypatch.setattr(house, "pick_model", pick)


def test_house_from_sources_builds_the_model_and_returns_questions(tools, monkeypatch):
    reg, models, ctx = tools
    fake_ask(monkeypatch, RAW)

    async def go():
        img = await stored_image()
        return await reg.tools["house_from_sources"].handler({"image_ids": [img["id"]], "notes": "dum"})

    res = run(go())
    assert res["ok"] and res["model_id"] == "house" and "Living" in res["summary"] and "Where is the door?" in res["open_questions"]
    assert models.store.load("house").parts and any(m["t"] == "scene" for m in ctx.msgs)
    assert reg.tools["house_from_sources"].long and reg.tools["house_refine"].long


def test_house_from_sources_reports_unusable_sources(tools):
    reg, _, _ = tools
    assert "at least one" in run(reg.tools["house_from_sources"].handler({}))["error"]


def test_house_refine_proposes_changes_without_regenerating(tools, monkeypatch):
    reg, models, ctx = tools
    fake_ask(monkeypatch, RAW)

    async def build():
        img = await stored_image()
        await reg.tools["house_from_sources"].handler({"image_ids": [img["id"]]})
        return img

    img = run(build())
    before = models.store.load("house")
    fake_ask(monkeypatch, {"observations": [{"room": "Kitchen", "floor_color": "#aa8855", "furniture": [{"kind": "table"}]},
                                              {"room": "Garage", "furniture": []}], "open_questions": ["Is the table fixed?"]})
    res = run(reg.tools["house_refine"].handler({"image_ids": [img["id"]]}))
    assert res["ok"] and res["proposal"] and "ground-floor-kitchen" in res["diff"] and res["skipped"] == ["no modelled room matches 'Garage'"]
    assert res["open_questions"] == ["Is the table fixed?"]
    assert models.store.load("house").to_dict() == before.to_dict()  # nothing changed until accept
    run(reg.tools["model_accept"].handler({"proposal": res["proposal"]}))
    after = models.store.load("house")
    assert after.parts["ground-floor-kitchen"].color == "#aa8855" and set(before.parts) <= set(after.parts)
    assert any(p.props.get("furniture") == "table" for p in after.parts.values())


def test_house_refine_without_a_house_or_difference(tools, monkeypatch):
    reg, models, _ = tools
    assert "error" in run(reg.tools["house_refine"].handler({"image_ids": ["x"]}))  # no 'house' model yet
    fake_ask(monkeypatch, RAW)

    async def go():
        img = await stored_image()
        await reg.tools["house_from_sources"].handler({"image_ids": [img["id"]]})
        fake_ask(monkeypatch, {"observations": [], "open_questions": []})
        return await reg.tools["house_refine"].handler({"image_ids": [img["id"]]})

    assert run(go())["proposal"] is None
    m = models.store.load("house")
    assert changes_from(m, {"observations": [{"room": "living", "floor_color": None, "floor_material": None, "furniture": ["sofa", "sofa"]}]})[0]
