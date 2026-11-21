# backend/tests/test_memory_focus.py
import asyncio
import json
import time

import pytest
from memory_fakes import MEMORY, ROUTES, SESSION, iso, run

from app.memory import focus, graph, handlers
from app.memory.tools import register_memory_tools
from app.tools_friday import Ctx
from app.voice.tools import ToolRegistry

OBS_HIT = {"obsId": "obs_9", "sessionId": SESSION["id"], "timestamp": iso(1), "title": "conversation", "score": 0.9}
MEM_HIT = {"obsId": MEMORY["id"], "sessionId": "memory", "timestamp": iso(1), "title": "Friday core", "score": 1.2}
EXPANDED = {"results": [
    {"obsId": "obs_9", "observation": {"narrative": "Built the orbs\x00\x1b[31m view " + "x" * 300, "concepts": ["Orbs"],
                                       "files": ["/work/u/a.py"]}},
    {"obsId": MEMORY["id"], "observation": {"title": "Friday core " + "T" * 200, "facts": ["Friday is a Jarvis"]}},
]}


@pytest.fixture
def smart(server, monkeypatch):
    async def fake_expand(query, hits):
        return {r["obsId"]: r["observation"] for r in EXPANDED["results"]}

    def install(hits):
        server({**ROUTES, ("POST", "/smart-search"): {"results": hits}})
        monkeypatch.setattr(focus.awareness, "expand_hits", fake_expand)

    return install


def test_focused_graph_maps_hits_to_node_ids_and_highlights(smart):
    smart([OBS_HIT, MEM_HIT])
    data = run(focus.focused_graph("Friday"))
    ids = {n["id"] for n in data["nodes"]}
    assert data["highlight"][0] == MEMORY["id"]  # best score first, same id as the generic graph
    assert f"session:{SESSION['id']}" in data["highlight"] and "gn_1" in data["highlight"]  # concept via concepts[]
    assert set(data["highlight"]) <= ids
    assert all(lk["source"] in ids and lk["target"] in ids for lk in data["links"])
    assert {h["kind"] for h in data["hits"]} == {"memory", "session"}
    assert data["query"] == "Friday" and data["summary"].startswith("K dotazu 'Friday'")
    assert all(set(n) == {"id", "label", "kind", "weight", "ts", "project"} for n in data["nodes"])


def test_focused_graph_sanitises_and_caps_text(smart):
    smart([OBS_HIT, MEM_HIT])
    data = run(focus.focused_graph("Friday"))
    for h in data["hits"]:
        assert len(h["snippet"]) <= 160 and len(h["label"]) <= 80
        assert not any(ord(c) < 32 or 127 <= ord(c) < 160 for c in h["snippet"] + h["label"])
    assert all(len(n["label"]) <= 80 for n in data["nodes"])
    assert len(data["summary"]) <= 400 and len(data["hits"]) <= 12


def test_focused_graph_creates_missing_nodes(smart):
    ghost = {"obsId": "mem_new", "sessionId": "memory", "timestamp": iso(1), "title": "Friday ghost", "score": 2}
    smart([ghost])
    data = run(focus.focused_graph("Friday"))
    assert [n["id"] for n in data["nodes"] if n["id"] == "mem_new"] == ["mem_new"]


def test_focused_graph_caps_nodes_hits_first(smart, monkeypatch):
    monkeypatch.setattr(focus, "FOCUS_MAX_NODES", 3)
    smart([OBS_HIT, MEM_HIT])
    data = run(focus.focused_graph("Friday"))
    assert len(data["nodes"]) == 3 and data["highlight"][0] == MEMORY["id"] and len(data["highlight"]) <= 3


def test_focused_graph_unrelated_hits_are_empty(smart):
    smart([OBS_HIT, MEM_HIT])  # vector search returns nearest neighbours even for nonsense
    data = run(focus.focused_graph("zzzzqqqx"))
    assert data["nodes"] == [] and data["highlight"] == [] and data["summary"].startswith("Nic nenalezeno")


def test_focused_graph_empty_result(smart):
    smart([])
    data = run(focus.focused_graph("zzzzqqqx"))
    assert data["nodes"] == [] and data["highlight"] == [] and data["links"] == [] and data["hits"] == []
    assert data["summary"].startswith("Nic nenalezeno k dotazu 'zzzzqqqx'")


def test_tool_schema_and_focused_result(smart):
    smart([OBS_HIT, MEM_HIT])
    sent: list[dict] = []

    async def emit(msg):
        sent.append(msg)

    registry = ToolRegistry()
    register_memory_tools(registry, Ctx(None, emit))  # pyright: ignore[reportArgumentType]
    tool = registry.tools["show_memory_graph"]
    assert tool.long and tool.scheduling == "WHEN_IDLE"
    assert set(tool.parameters["properties"]) == {"query", "project", "days"}
    assert "what was done" in tool.description and "aloud" in tool.description and "highlights" in tool.description
    json.dumps(tool.parameters)
    out = run(tool.handler({"query": "Friday"}))
    assert out["ok"] and out["highlight_count"] >= 2 and out["summary"] and sent[0]["data"]["hits"]
    plain = run(tool.handler({}))
    assert "highlight_count" not in plain and "highlight" not in sent[1]["data"]


def test_memory_search_handler_emits_notice_then_view(smart):
    smart([MEM_HIT])
    sent: list[dict] = []

    async def send(m):
        sent.append(m)

    run(handlers.memory_search(send, {"t": "memory_search", "query": " Friday "}))
    assert [m["t"] for m in sent] == ["notice", "view"] and sent[0]["text"] == "Hledam v pameti..."
    assert sent[1]["kind"] == "memory_graph" and sent[1]["data"]["query"] == "Friday"
    sent.clear()
    run(handlers.memory_search(send, {"t": "memory_search"}))
    assert [m["t"] for m in sent] == ["error"]


def test_stale_graph_is_served_instantly_and_refreshed(server, monkeypatch):
    server(ROUTES)
    build_calls = []
    real = graph._build

    async def slow_build():
        build_calls.append(1)
        await asyncio.sleep(0.3)
        return await real()

    monkeypatch.setattr(graph, "_build", slow_build)

    async def scenario():
        await graph.cached_graph()
        old = graph._cache["graph"]
        graph._cache["graph"] = (time.time() - graph.CACHE_S - 5, old[1])
        t0 = time.perf_counter()
        got = await graph.cached_graph()
        fast = time.perf_counter() - t0
        await graph.cached_graph()  # second caller must not start another build
        await asyncio.sleep(0.5)
        return got is old[1], fast, graph._cache["graph"][0] > time.time() - 5

    same, fast, refreshed = asyncio.run(scenario())
    assert same and fast < 0.1 and refreshed and len(build_calls) == 2
