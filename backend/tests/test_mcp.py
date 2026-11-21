# backend/tests/test_mcp.py
"""MCP client against an in-process fake server: discovery, allowlist, approval gating, trimming, schemas."""

import asyncio
import json
from contextlib import asynccontextmanager

from mcp import Client
from mcp.server import MCPServer

from app.mcp.config import ServerSpec
from app.mcp.hub import McpPool
from app.mcp.router import MAX_RESULT_CHARS
from app.voice.tools import ToolRunner

CALLS: list[tuple[str, dict]] = []


def fake_server() -> MCPServer:
    server = MCPServer("fake")

    @server.tool()
    def read_thing(name: str, limit: int | None = None) -> str:
        "Read something"
        CALLS.append(("read_thing", {"name": name}))
        return "x" * 10000 if name == "big" else f"thing {name}"

    @server.tool()
    def delete_thing(name: str) -> str:
        "Delete something"
        CALLS.append(("delete_thing", {"name": name}))
        return "deleted"

    @server.tool()
    def secret_tool() -> str:
        "Not on the allowlist"
        return "no"

    return server


@asynccontextmanager
async def connector(spec):
    async with Client(fake_server()) as client:
        yield client


def spec(**kw) -> ServerSpec:
    base = {"name": "fake", "url": "http://fake.test", "allowed_tools": ("read_thing", "delete_thing"),
            "policies": {"read_thing": {"risky": False}}}
    return ServerSpec(**{**base, **kw})


async def make_hub(**kw) -> McpPool:
    hub = McpPool([spec(**kw)], connector)
    await hub.discover()
    return hub


class Asker:
    def __init__(self, answer: bool):
        self.answer, self.asked = answer, []

    async def ask(self, name, summary, args):
        self.asked.append((name, summary))
        return self.answer


def runner(hub, answer: bool):
    asker = Asker(answer)
    sent = []

    async def emit(msg):
        sent.append(msg)

    from app.voice.tools import ToolRegistry

    registry = ToolRegistry()
    hub._add(registry)
    return ToolRunner(registry, None, emit, asker), asker  # pyright: ignore[reportArgumentType]


def call(name, args):
    from google.genai import types

    return types.FunctionCall(id="c1", name=name, args=args)


def test_discovery_and_allowlist_hide_unlisted_tools():
    async def go():
        hub = await make_hub()
        names = sorted(t.name for t in hub.tools())
        status = await hub.status()
        await hub.close()
        return names, status["servers"][0]

    names, st = asyncio.run(go())
    assert names == ["fake__delete_thing", "fake__read_thing"]
    assert st["discovered"] == 3 and st["blocked"] == ["secret_tool"] and st["connected"] is True
    assert "token" not in json.dumps(st).lower()


def test_empty_allowlist_exposes_nothing():
    async def go():
        hub = await make_hub(allowed_tools=())
        out = hub.tools()
        await hub.close()
        return out

    assert asyncio.run(go()) == []


def test_risky_by_default_and_explicit_read_only():
    async def go():
        hub = await make_hub()
        tools = {t.name: t for t in hub.tools()}
        await hub.close()
        return tools

    tools = asyncio.run(go())
    assert tools["fake__delete_thing"].risky and not tools["fake__read_thing"].risky
    assert "fake / delete_thing" in tools["fake__delete_thing"].confirm_summary({"name": "a" * 500})  # pyright: ignore
    assert len(tools["fake__delete_thing"].confirm_summary({"name": "a" * 500})) < 250  # pyright: ignore


def test_denied_risky_call_never_reaches_the_server():
    async def go():
        hub = await make_hub()
        run, asker = runner(hub, answer=False)
        CALLS.clear()
        out = await run._execute(run.registry.tools["fake__delete_thing"], call("fake__delete_thing", {"name": "z"}))
        await hub.close()
        return out, asker.asked

    out, asked = asyncio.run(go())
    assert out == {"error": "denied by user"} and CALLS == [] and asked[0][0] == "fake__delete_thing"


def test_approved_risky_call_and_read_only_call_without_prompt():
    async def go():
        hub = await make_hub()
        run, asker = runner(hub, answer=True)
        CALLS.clear()
        deleted = await run._execute(run.registry.tools["fake__delete_thing"], call("fake__delete_thing", {"name": "z"}))
        read = await run._execute(run.registry.tools["fake__read_thing"], call("fake__read_thing", {"name": "q"}))
        await hub.close()
        return deleted, read, asker.asked

    deleted, read, asked = asyncio.run(go())
    assert "deleted" in deleted["result"] and "thing q" in read["result"]
    assert len(asked) == 1 and "untrusted" in read["note"]
    assert read["result"].startswith('<mcp-result server="fake" tool="read_thing">')


def test_long_results_are_trimmed():
    async def go():
        hub = await make_hub()
        tool = {t.name: t for t in hub.tools()}["fake__read_thing"]
        out = await tool.handler({"name": "big"})
        await hub.close()
        return out

    out = asyncio.run(go())
    assert "[truncated]" in out["result"] and len(out["result"]) < MAX_RESULT_CHARS + 200


def test_allowed_names_policy_blocks_other_names():
    async def go():
        hub = await make_hub(policies={"read_thing": {"risky": False, "allowed_names": ["ok"]}})
        tool = {t.name: t for t in hub.tools()}["fake__read_thing"]
        bad, good = await tool.handler({"name": "evil"}), await tool.handler({"name": "ok"})
        await hub.close()
        return tool, bad, good

    tool, bad, good = asyncio.run(go())
    assert "error" in bad and "thing ok" in good["result"] and "Allowed names: ok" in tool.description


def test_unreachable_server_is_reported_and_calls_fail_softly():
    @asynccontextmanager
    async def broken(_spec):
        raise ConnectionError("refused")
        yield

    async def go():
        hub = McpPool([spec()], broken)
        await hub.discover()
        status = await hub.status()
        return status["servers"][0], hub.tools()

    st, tools = asyncio.run(go())
    assert st["connected"] is False and "ConnectionError" in st["error"] and tools == []


def test_status_endpoint(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.mcp import hub as shared

    monkeypatch.setattr(shared, "_clients", None)
    monkeypatch.setattr(shared, "_specs", [spec(url=None)])
    body = TestClient(app).get("/api/mcp/status").json()
    assert body["servers"][0]["enabled"] is False
    monkeypatch.setattr(shared, "_clients", None)
    monkeypatch.setattr(shared, "_specs", None)


def test_agent_session_gates_risky_mcp_tool():
    from app.agent_wiring import AgentSession
    from app.scene import SceneStore
    from app.voice.tools import ToolRegistry

    async def go():
        hub = await make_hub()
        session = AgentSession(SceneStore(), lambda m: asyncio.sleep(0), ToolRegistry())
        hub._add(session.registry)
        session.approvals = Asker(False)  # pyright: ignore[reportAttributeAccessIssue]
        CALLS.clear()
        out = await session.worker_tools()["fake__delete_thing"].handler({"name": "z"})
        await hub.close()
        return out

    out = asyncio.run(go())
    assert out == {"error": "denied by user"} and CALLS == []
