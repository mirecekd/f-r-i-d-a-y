# backend/tests/test_workshop_look_tool.py
"""The workshop_look tool with a fake browser and a fake vision model (no network)."""

import asyncio
import json
from pathlib import Path

from app.scene import SceneStore
from app.tools_friday.ctx import Ctx
from app.vision import store as image_store
from app.voice.tools import ToolRegistry
from app.workshop import look_tools
from app.workshop.look import NO_ANSWER, SnapshotBroker
from app.workshop.messages import handle_workshop_message
from app.workshop.tools import register_workshop_tools
from tests.look_helpers import good

VASE = json.loads((Path(__file__).parent / "fixtures" / "workshop" / "vase.json").read_text(encoding="utf-8"))


def make_tool(monkeypatch, reply=good):
    sent: list[dict] = []
    holder: dict = {}

    async def emit(msg):
        sent.append(msg)
        if msg.get("t") == "workshop_snapshot_request":
            answer = reply(msg)
            if answer is not None:
                asyncio.get_running_loop().call_soon(
                    lambda: asyncio.ensure_future(handle_workshop_message(holder["s"], answer))
                )

    registry = ToolRegistry()
    session = register_workshop_tools(registry, Ctx(SceneStore(), emit))
    holder["s"] = session
    calls: list[tuple] = []

    async def fake_pick(pinned):
        calls.append(("pick", pinned))
        return "vision-model"

    async def fake_chat(model, messages, tools, on_delta=None):
        calls.append(("chat", model, messages))
        return {"text": " 1. part leg_2 floats above the seat. ", "calls": []}

    monkeypatch.setattr(look_tools, "pick_vision_model", fake_pick)
    monkeypatch.setattr(look_tools.llm, "chat", fake_chat)
    return registry, session, calls, sent


def test_tool_is_registered_with_the_other_workshop_tools(monkeypatch):
    registry, _, _, _ = make_tool(monkeypatch)
    assert "workshop_look" in registry.tools and "workshop_build" in registry.tools


def test_tool_result_shape_prompt_and_stored_image(monkeypatch):
    registry, session, calls, sent = make_tool(monkeypatch)

    async def go():
        await session.open(None, "Vase")
        await session.build(VASE)
        return await registry.tools["workshop_look"].handler({"question": "is it symmetric?"})

    out = asyncio.run(go())
    assert out["ok"] is True and out["critique"].startswith("1. part leg_2") and out["parts"] > 0
    assert image_store.load_meta(out["image_id"]) is not None
    kinds = [c[0] for c in calls]
    assert kinds == ["pick", "chat"] and calls[1][1] == "vision-model"
    text = calls[1][2][1]["content"][0]["text"]
    assert "3D CAD render of 'Vase'" in text and "is it symmetric?" in text and "height" in text
    assert "at most 8 concrete defects" in text
    assert calls[1][2][1]["content"][1]["type"] == "image_url"
    assert any(m.get("t") == "workshop_snapshot_request" for m in sent)


def test_tool_general_critique_when_no_question(monkeypatch):
    registry, session, calls, _ = make_tool(monkeypatch)

    async def go():
        await session.open(None, "Vase")
        await session.build(VASE)
        return await registry.tools["workshop_look"].handler({})

    assert asyncio.run(go())["ok"] is True
    assert "floating or overlapping parts" in calls[1][2][1]["content"][0]["text"]


def test_tool_errors_are_results_not_exceptions(monkeypatch):
    registry, session, calls, _ = make_tool(monkeypatch, reply=lambda m: None)
    handler = registry.tools["workshop_look"].handler

    async def go():
        no_workshop = await handler({})
        await session.open(None, "Empty")
        nothing_built = await handler({})
        await session.build(VASE)
        return no_workshop, nothing_built

    no_workshop, nothing_built = asyncio.run(go())
    assert "no workshop is open" in no_workshop["error"]
    assert "workshop_build" in nothing_built["error"]
    assert calls == []


def test_tool_timeout_is_clear_and_never_calls_the_model(monkeypatch):
    registry, session, calls, _ = make_tool(monkeypatch, reply=lambda m: None)
    real = SnapshotBroker.request

    async def quick(self, emit, workshop_id, width=800, timeout=8.0):
        return await real(self, emit, workshop_id, width, 0.05)

    monkeypatch.setattr(SnapshotBroker, "request", quick)

    async def go():
        await session.open(None, "Vase")
        await session.build(VASE)
        return await registry.tools["workshop_look"].handler({})

    out = asyncio.run(go())
    assert out == {"error": NO_ANSWER} and calls == []


def test_tool_survives_a_vision_failure_and_session_close_cancels_the_wait(monkeypatch):
    from app.agent.llm import LlmError

    registry, session, calls, _ = make_tool(monkeypatch)

    async def boom(model, messages, tools, on_delta=None):
        raise LlmError("no key")

    monkeypatch.setattr(look_tools.llm, "chat", boom)

    async def go():
        await session.open(None, "Vase")
        await session.build(VASE)
        return await registry.tools["workshop_look"].handler({})

    assert "the vision model failed" in asyncio.run(go())["error"]


def test_session_close_cancels_a_waiting_look(monkeypatch):
    registry, session, calls, _ = make_tool(monkeypatch, reply=lambda m: None)

    async def go():
        await session.open(None, "Vase")
        await session.build(VASE)
        handler = registry.tools["workshop_look"].handler

        async def look_once():
            return await handler({})

        task = asyncio.create_task(look_once())
        await asyncio.sleep(0.05)
        session.close()
        return await asyncio.wait_for(task, 1.0)

    out = asyncio.run(go())
    assert "closed before the snapshot arrived" in out["error"] and calls == []


def test_messages_route_snapshot_to_the_broker_and_hostile_message_is_silent(monkeypatch):
    _, session, _, sent = make_tool(monkeypatch)

    async def go():
        await handle_workshop_message(session, {"t": "workshop_snapshot", "req": "zzz", "id": "w", "jpeg_b64": "xx"})
        await handle_workshop_message(session, {"t": "workshop_snapshot"})

    asyncio.run(go())
    assert not [m for m in sent if m.get("t") == "error"]
