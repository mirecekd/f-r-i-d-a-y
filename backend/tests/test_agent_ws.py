# backend/tests/test_agent_ws.py
"""WebSocket wiring: models on connect, set_model persistence, text chat through the agent loop."""

import pytest
from fastapi.testclient import TestClient

from app import agent_wiring, main
from app.agent import loop
from app.agent.catalog import catalog
from app.voice.tools import Tool

ENTRIES = [
    {"id": "g1-live", "provider": "gemini", "label": "G1 Live", "group": "google live", "roles": ["chat"]},
    {"id": "l1", "provider": "litellm", "label": "L1", "group": "x", "roles": ["agent"]},
]


@pytest.fixture
def client(tmp_path, monkeypatch):

    async def fake_get():
        return ENTRIES

    monkeypatch.setattr(catalog, "get", fake_get)
    monkeypatch.setattr(catalog, "_entries", {"all": (0.0, ENTRIES)})
    return TestClient(main.app)


def drain(ws, until):
    seen = []
    while True:
        msg = ws.receive_json()
        seen.append(msg)
        if until(msg):
            return seen


def test_models_on_connect_and_set_model_persists(client):
    with client.websocket_connect("/ws") as ws:
        first = drain(ws, lambda m: m["t"] == "models")[-1]
        assert first["catalog"] == ENTRIES
        assert first["pinned"]["agent_model"] == agent_wiring.DEFAULT_MODEL
        ws.send_json({"t": "set_model", "role": "agent", "model": "l1"})
        echoed = drain(ws, lambda m: m["t"] == "models")[-1]
        assert echoed["pinned"]["agent_model"] == "l1"
        ws.send_json({"t": "set_model", "role": "chat", "model": "nope"})
        assert "unknown model" in drain(ws, lambda m: m["t"] == "error")[-1]["message"]
        ws.send_json({"t": "set_model", "role": "chat", "model": "l1"})  # agent-only model for the chat role
        assert "not available for role chat" in drain(ws, lambda m: m["t"] == "error")[-1]["message"]
        ws.send_json({"t": "set_model", "role": "agent", "model": "g1-live"})  # live model for the agent role
        assert "not available for role agent" in drain(ws, lambda m: m["t"] == "error")[-1]["message"]
    with client.websocket_connect("/ws") as ws:
        assert drain(ws, lambda m: m["t"] == "models")[-1]["pinned"]["agent_model"] == "l1"


def chat_once(client):
    with client.websocket_connect("/ws") as ws:
        drain(ws, lambda m: m["t"] == "models")
        ws.send_json({"t": "set_model", "role": "chat", "model": "g1-live"})
        drain(ws, lambda m: m["t"] == "models")
        ws.send_json({"t": "chat", "text": "hello"})
        return drain(ws, lambda m: m == {"t": "state", "state": "idle"})


def test_text_chat_uses_pinned_live_model(client, monkeypatch):
    seen = {}

    async def fake_turn(model, history, tools, emit, on_delta):
        seen["model"], seen["tools"] = model, list(tools)
        await on_delta("hi ")
        await on_delta("there")
        return "hi there"

    monkeypatch.setattr(agent_wiring.live_text, "run_turn", fake_turn)
    deltas = [m for m in chat_once(client) if m["t"] == "chat_delta"]
    assert "".join(d["text"] for d in deltas) == "hi there"
    assert len({d["id"] for d in deltas}) == 1
    assert seen["model"] == "g1-live" and "draw" not in seen["tools"]


def test_text_chat_falls_back_to_agent_path_when_live_turn_fails(client, monkeypatch):
    seen = {}

    async def failing_turn(model, history, tools, emit, on_delta):
        raise RuntimeError("live down")

    async def fake_chat(model, messages, tools, on_delta=None):
        seen["model"] = model
        if on_delta:
            await on_delta("fallback")
        return {"text": "fallback", "tool_calls": []}

    monkeypatch.setattr(agent_wiring.live_text, "run_turn", failing_turn)
    monkeypatch.setattr(loop.llm, "chat", fake_chat)
    deltas = [m for m in chat_once(client) if m["t"] == "chat_delta"]
    assert "".join(d["text"] for d in deltas) == "fallback"
    assert seen["model"] == agent_wiring.pinned_model("agent")


def test_session_registers_draw_and_hides_it_from_the_agent():
    async def noop(ev):
        pass

    base = main.tool_registry
    session = agent_wiring.AgentSession(main.scene, noop, base)
    assert session.registry.tools["draw"].long
    assert "draw" not in session.worker_tools()
    assert "draw" not in base.tools  # per-connection registry, the shared one is untouched
    assert isinstance(session.registry.tools["draw"], Tool)
