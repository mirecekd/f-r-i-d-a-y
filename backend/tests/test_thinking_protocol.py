# backend/tests/test_thinking_protocol.py
"""Thinking level over the wire (`models`, `set_thinking`) and the Live connect-failure path of the bridge."""

import asyncio
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient

from app import main
from app.agent import prefs, thinking
from app.agent.catalog import catalog
from app.voice import ToolRegistry, VoiceBridge, session
from app.voice import bridge as bridge_mod


@pytest.fixture(autouse=True)
def clean_tables(monkeypatch):
    monkeypatch.delenv("FRIDAY_THINKING", raising=False)
    monkeypatch.setattr(thinking.LIVE, "no_config", set(thinking.LIVE.no_config))
    monkeypatch.setattr(thinking.LIVE, "bad_levels", {k: set(v) for k, v in thinking.LIVE.bad_levels.items()})


ENTRIES = [{"id": "g1-live", "provider": "gemini", "label": "G1", "group": "google live", "roles": ["chat"]}]


@pytest.fixture
def client(monkeypatch):
    async def fake_get():
        return ENTRIES

    monkeypatch.setattr(catalog, "get", fake_get)
    monkeypatch.setattr(catalog, "_entries", {"all": (0.0, ENTRIES)})
    return TestClient(main.app)


def next_of(ws, kind):
    while True:
        msg = ws.receive_json()
        if msg["t"] == kind:
            return msg


def test_models_message_and_set_thinking(client):
    with client.websocket_connect("/ws") as ws:
        first = next_of(ws, "models")
        assert first["thinking"] == "high" and first["thinking_levels"] == ["minimal", "low", "medium", "high", "max"]
        ws.send_json({"t": "set_thinking", "level": "low"})
        assert next_of(ws, "models")["thinking"] == "low"
        ws.send_json({"t": "set_thinking", "level": "extreme"})
        assert "unknown level" in next_of(ws, "error")["message"]
    assert prefs.thinking() == "low"


def test_set_thinking_during_voice_session_emits_notice():
    from app.agent_wiring import AgentSession
    from app.scene import SceneStore

    events: list[dict] = []

    async def emit(m):
        events.append(m)

    async def go():
        agent = AgentSession(SceneStore(), emit, ToolRegistry())
        await agent.set_thinking({"level": "medium"}, voice_active=True)

    asyncio.run(go())
    assert events[0]["t"] == "models" and events[0]["thinking"] == "medium"
    assert events[1]["t"] == "notice"


def run_bridge(monkeypatch, error: Exception, learn_to_pass: bool = False):
    events: list[dict] = []
    attempts: list[int] = []
    monkeypatch.setattr(bridge_mod, "BACKOFF_BASE_S", 0)

    @asynccontextmanager
    async def fake_connect(_registry, handle=None, briefing="", profile="headphones"):
        attempts.append(1)
        raise error
        yield

    monkeypatch.setattr(session, "connect", fake_connect)

    async def send_json(m):
        events.append(m)

    async def send_bytes(_):
        pass

    async def go():
        bridge = VoiceBridge(send_json, send_bytes, ToolRegistry())
        await asyncio.wait_for(bridge.start(), 3)

    asyncio.run(go())
    return events, attempts


def test_bridge_connect_failure_emits_readable_error_and_idle(monkeypatch):
    monkeypatch.setenv("GEMINI_LIVE_MODEL", "gemini-3.8-live")
    events, attempts = run_bridge(monkeypatch, RuntimeError("1007 None. Unsupported language code"))
    err = next(e for e in events if e["t"] == "error")
    assert "gemini-3.8-live" in err["message"] and "did not accept the connection" in err["message"]
    assert events[-1] == {"t": "state", "state": "idle"} and len(attempts) == 1


def test_bridge_retries_once_after_learning_a_thinking_rejection(monkeypatch):
    monkeypatch.setenv("GEMINI_LIVE_MODEL", "gemini-9-live")
    events, attempts = run_bridge(monkeypatch, RuntimeError("1007 None. Thinking level is not supported for this model."))
    assert len(attempts) == 2 and thinking.live_config("gemini-9-live") is None
    assert any(e["t"] == "error" for e in events)
