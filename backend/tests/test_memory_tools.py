# backend/tests/test_memory_tools.py
import json

import pytest
from memory_fakes import ROUTES, iso, run

from app.memory import graph
from app.memory.tools import register_memory_tools
from app.tools_friday import Ctx
from app.views import VIEW_KINDS
from app.voice.tools import ToolRegistry


def test_graph_shape_and_links_reference_nodes(server):
    server(ROUTES)
    data = run(graph.memory_graph())
    kinds = {n["kind"] for n in data["nodes"]}
    assert kinds == {"project", "session", "memory", "concept", "file"}
    ids = {n["id"] for n in data["nodes"]}
    assert data["links"] and all(lk["source"] in ids and lk["target"] in ids for lk in data["links"])
    assert {lk["kind"] for lk in data["links"]} >= {"in", "seen_in", "uses", "tagged"}
    assert all(set(n) == {"id", "label", "kind", "weight", "ts", "project"} for n in data["nodes"])
    orbs = next(n for n in data["nodes"] if n["id"] == "gn_1")
    assert orbs["project"] == "FRIDAY"


def test_graph_is_capped_and_cached(server):
    nodes = [
        {"id": f"gn_{i}", "name": f"n{i}", "type": "concept", "createdAt": iso(i / 100), "sourceObservationIds": []}
        for i in range(500)
    ]
    many = {"nodes": nodes, "edges": []}
    fake = server({**ROUTES, ("POST", "/graph/query"): many})
    first = run(graph.memory_graph())
    assert len(first["nodes"]) == graph.MAX_NODES
    assert {"gn_0", "gn_1"} <= {n["id"] for n in first["nodes"]}
    run(graph.memory_graph(project="FRIDAY"))
    assert sum(1 for c in fake.calls if c[1].endswith("/graph/query")) == 1


def test_filter_graph_by_project_and_query():
    g = {"nodes": [{"id": "a", "label": "Alpha", "project": "P"}, {"id": "b", "label": "Beta", "project": "P"},
                   {"id": "c", "label": "Gamma", "project": "Q"}],
         "links": [{"source": "a", "target": "b"}, {"source": "b", "target": "c"}]}
    assert [n["id"] for n in graph.filter_graph(g, project="P")["nodes"]] == ["a", "b"]
    assert [n["id"] for n in graph.filter_graph(g, query="gamma")["nodes"]] == ["b", "c"]


@pytest.fixture
def tools():
    sent: list[dict] = []

    async def emit(msg):
        sent.append(msg)

    registry = ToolRegistry()
    register_memory_tools(registry, Ctx(None, emit))  # pyright: ignore[reportArgumentType]
    return registry, sent


def test_tool_schemas(tools):
    registry, _ = tools
    assert set(registry.tools) == {"recall", "today_digest", "remember", "show_memory_graph"}
    assert registry.tools["recall"].long and registry.tools["recall"].scheduling == "WHEN_IDLE"
    assert registry.tools["today_digest"].long and not registry.tools["remember"].long
    assert "only when the user asks" in registry.tools["remember"].description
    assert registry.tools["recall"].parameters["required"] == ["query"]
    assert "memory_graph" in VIEW_KINDS
    for t in registry.tools.values():
        json.dumps(t.parameters)


def test_recall_tool_wraps_result_as_data(server, tools):
    registry, _ = tools
    server({("POST", "/smart-search"): {"results": [{"obsId": "mem_1", "timestamp": iso(1), "title": "x", "score": 1}]}})
    out = run(registry.tools["recall"].handler({"query": "x"}))
    assert out["memory"].startswith("<memory-data>") and out["memory"].endswith("</memory-data>")
    assert "not instructions" in out["notice"]
    assert "query" in run(registry.tools["recall"].handler({}))["error"]


def test_tools_return_error_when_memory_down(server, tools):
    registry, sent = tools
    server({})
    assert "error" in run(registry.tools["today_digest"].handler({}))
    assert "error" in run(registry.tools["show_memory_graph"].handler({}))
    assert "error" in run(registry.tools["remember"].handler({"content": "x"}))
    assert sent == []


def test_remember_posts_content_and_project(server, tools):
    registry, _ = tools
    fake = server({("POST", "/remember"): {"memory": {"id": "mem_9"}}})
    assert run(registry.tools["remember"].handler({"content": "use JWT", "project": "FRIDAY"})) == {"ok": True, "id": "mem_9"}
    assert json.loads(fake.calls[0][3]) == {"content": "use JWT", "project": "FRIDAY"}


def test_show_memory_graph_emits_view(server, tools):
    registry, sent = tools
    server(ROUTES)
    out = run(registry.tools["show_memory_graph"].handler({"project": "FRIDAY"}))
    assert out["ok"] and out["nodes"] == len(sent[0]["data"]["nodes"])
    assert sent[0]["t"] == "view" and sent[0]["kind"] == "memory_graph" and sent[0]["id"] == out["id"]
