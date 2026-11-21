# backend/tests/test_memory_handlers.py
import asyncio
from unittest.mock import AsyncMock

from app.memory import client, handlers

GRAPH = {"nodes": [{"id": "a", "label": "A", "kind": "project", "weight": 1, "ts": 0, "project": "A"}], "links": []}


def _collect(monkeypatch, fake: AsyncMock, msg: dict) -> list[dict]:
    sent: list[dict] = []

    async def send(m):
        sent.append(m)

    monkeypatch.setattr(handlers.graph, "memory_graph", fake)
    asyncio.run(handlers.show_memory_graph(send, msg))
    return sent


def test_show_memory_graph_sends_notice_then_view(monkeypatch):
    fake = AsyncMock(return_value=GRAPH)
    sent = _collect(monkeypatch, fake, {"t": "show_memory_graph"})
    assert [m["t"] for m in sent] == ["notice", "view"]
    assert sent[0]["text"] == "Nacitam pamet..."
    assert sent[1]["kind"] == "memory_graph" and sent[1]["data"] == GRAPH
    fake.assert_awaited_once_with(None, None)


def test_show_memory_graph_passes_filters_and_reports_unavailable(monkeypatch):
    fake = AsyncMock(side_effect=client.MemoryUnavailable("agentmemory is down"))
    sent = _collect(monkeypatch, fake, {"t": "show_memory_graph", "project": " FRIDAY ", "query": ""})
    fake.assert_awaited_once_with("FRIDAY", None)
    assert [m["t"] for m in sent] == ["notice", "error"]
    assert "down" in sent[1]["message"]
