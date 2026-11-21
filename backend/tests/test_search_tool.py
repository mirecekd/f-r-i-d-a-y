# backend/tests/test_search_tool.py
"""web_search against a fake Gemini client: shape, caps, delimiting and error handling."""

import asyncio
from types import SimpleNamespace as NS

from app.agent_wiring import AgentSession
from app.scene import SceneStore
from app.tools_friday import search
from app.voice.tools import ToolRegistry


def chunk(i):
    return NS(web=NS(uri=f"https://e.test/{i}", title=f"T{i}"))


CALLS: list[dict] = []


def fake_client(response=None, error=None):
    async def generate_content(**kw):
        CALLS.append(kw)
        if error:
            raise error
        return response

    return NS(aio=NS(models=NS(generate_content=generate_content)))


def reply(text, chunks):
    return NS(text=text, candidates=[NS(grounding_metadata=NS(grounding_chunks=chunks))])


def test_answer_is_capped_delimited_and_sources_limited(monkeypatch):
    chunks = [chunk(i) for i in range(8)] + [chunk(0)]
    monkeypatch.setattr(search, "_client", lambda: fake_client(reply("x" * 3000, chunks)))
    out = asyncio.run(search.web_search({"query": "weather"}))
    assert out["answer"].startswith("<web-search-result>\n") and out["answer"].endswith("\n</web-search-result>")
    assert len(out["answer"]) == 1500 + len("<web-search-result>\n\n</web-search-result>")
    assert [s["url"] for s in out["sources"]] == [f"https://e.test/{i}" for i in range(5)]
    assert "untrusted" in out["note"]
    cfg = CALLS[-1]["config"]
    assert cfg.tools[0].google_search is not None and CALLS[-1]["contents"] == "weather"


def test_errors_become_payloads(monkeypatch):
    assert asyncio.run(search.web_search({"query": " "})) == {"error": "empty query"}
    monkeypatch.setattr(search, "_client", lambda: fake_client(error=RuntimeError("boom secret")))
    out = asyncio.run(search.web_search({"query": "q"}))
    assert out == {"error": "search failed (RuntimeError)"}
    monkeypatch.setattr(search, "_client", lambda: fake_client(reply("", [])))
    assert "error" in asyncio.run(search.web_search({"query": "q"}))


def test_registered_per_connection_and_not_risky():
    async def emit(msg):
        pass

    session = AgentSession(SceneStore(), emit, ToolRegistry())
    tool = session.registry.tools["web_search"]
    assert not tool.risky and "web_search" in session.worker_tools()
