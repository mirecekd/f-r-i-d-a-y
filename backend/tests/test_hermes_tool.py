# backend/tests/test_hermes_tool.py
"""ask_hermes against a mocked HTTP transport, plus registration rules and approval gating in AgentSession."""

import asyncio
import json

import httpx

from app.agent_wiring import AgentSession
from app.scene import SceneStore
from app.tools_friday import hermes
from app.voice.tools import ToolRegistry

REAL_CLIENT = httpx.AsyncClient


def mock_hermes(monkeypatch, handler) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    monkeypatch.setattr(hermes.httpx, "AsyncClient", lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(respond)))
    monkeypatch.setenv("HERMES_URL", "http://hermes.test/v1/")
    monkeypatch.setenv("HERMES_KEY", "unit-test-credential")
    monkeypatch.delenv("HERMES_MODEL", raising=False)
    return seen


def test_ask_hermes_request_shape_and_result(monkeypatch):
    body = {"choices": [{"message": {"content": "Ctyri."}}]}
    seen = mock_hermes(monkeypatch, lambda r: httpx.Response(200, json=body))
    out = asyncio.run(hermes.ask_hermes({"request": "Kolik je 2+2?"}))
    assert out == {"result": "Ctyri."}
    req = seen[0]
    assert str(req.url) == "http://hermes.test/v1/chat/completions"
    assert req.headers["authorization"] == "Bearer unit-test-credential"
    assert req.headers["x-hermes-session-id"] == "friday"
    sent = json.loads(req.content)
    assert sent["model"] == "hermes-agent"
    assert sent["messages"][0]["content"].endswith("Kolik je 2+2?")
    assert "tabletu" in sent["messages"][0]["content"]


def test_ask_hermes_errors_become_payloads(monkeypatch):
    mock_hermes(monkeypatch, lambda r: httpx.Response(500))
    assert "unavailable" in asyncio.run(hermes.ask_hermes({"request": "x"}))["error"]

    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    mock_hermes(monkeypatch, slow)
    assert "did not answer" in asyncio.run(hermes.ask_hermes({"request": "x"}))["error"]
    assert asyncio.run(hermes.ask_hermes({"request": "  "})) == {"error": "empty request"}


def test_registered_only_with_url_and_key(monkeypatch):
    monkeypatch.delenv("HERMES_URL", raising=False)
    monkeypatch.setenv("HERMES_KEY", "k")
    registry = ToolRegistry()
    hermes.register_hermes_tool(registry)
    assert "ask_hermes" not in registry.tools
    monkeypatch.setenv("HERMES_URL", "http://hermes.test/v1")
    hermes.register_hermes_tool(registry)
    tool = registry.tools["ask_hermes"]
    assert tool.long and tool.risky and tool.confirm_summary
    assert tool.confirm_summary({"request": "Posli zpravu"}) == "Ask Hermes: Posli zpravu"


def test_text_chat_path_asks_before_running_risky_tool(monkeypatch):
    seen = mock_hermes(monkeypatch, lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}))

    async def go():
        sent: list[dict] = []

        async def emit(msg: dict) -> None:
            sent.append(msg)

        session = AgentSession(SceneStore(), emit, ToolRegistry())
        tool = session.worker_tools()["ask_hermes"]
        task = asyncio.create_task(tool.handler({"request": "Smaz vsechno"}))
        while not any(m["t"] == "confirm_request" for m in sent):
            await asyncio.sleep(0.005)
        assert not seen  # nothing left the server before approval
        session.approvals.resolve({"t": "confirm", "id": sent[-1]["id"], "allow": False})
        assert await task == {"error": "denied by user"}
        assert not seen

    asyncio.run(go())
