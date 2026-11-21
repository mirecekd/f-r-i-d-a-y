# backend/tests/memory_fakes.py
"""Shared fakes for the agentmemory tests: a routed httpx.MockTransport server and sample records."""

import asyncio
from datetime import UTC, datetime, timedelta

import httpx


def iso(hours_ago: float = 0) -> str:
    return (datetime.now(UTC) - timedelta(hours=hours_ago)).isoformat().replace("+00:00", "Z")


class FakeServer:
    """Routes (method, path) to JSON replies and records every call."""

    def __init__(self, routes: dict[tuple[str, str], object]):
        self.routes, self.calls = routes, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, request.url.path, request.headers.get("authorization"), request.content))
        reply = self.routes.get((request.method, request.url.path.removeprefix("/agentmemory")))
        if reply is None:
            return httpx.Response(404, json={"error": "nope"})
        if isinstance(reply, int):
            return httpx.Response(reply, json={"error": "boom"})
        return httpx.Response(200, json=reply)


def run(coro):
    return asyncio.run(coro)


SESSION = {"id": "0000-abcdef12", "project": "FRIDAY", "startedAt": iso(2), "updatedAt": iso(1), "observationCount": 9}
OBS = [
    {"type": "conversation", "title": "prompt_submit", "narrative": "Build the memory orbs", "importance": 5},
    {"type": "file_write", "title": "write", "importance": 5},
    {"type": "error", "title": "bash", "importance": 7},
]
MEMORY = {"id": "mem_1", "title": "Friday core", "project": "FRIDAY", "createdAt": iso(1), "strength": 7, "concepts": ["Orbs"]}
GRAPH = {
    "nodes": [
        {"id": "gn_1", "name": "Orbs", "type": "concept", "createdAt": iso(1), "sourceObservationIds": ["obs_1"]},
        {"id": "gn_2", "name": "a.py", "type": "file", "createdAt": iso(1), "sourceObservationIds": ["obs_1"]},
    ],
    "edges": [{"sourceNodeId": "gn_1", "targetNodeId": "gn_2", "type": "uses", "weight": 0.8}],
}
ROUTES = {
    ("GET", "/sessions"): {"sessions": [SESSION], "nextCursor": None},
    ("GET", "/observations"): {"observations": OBS},
    ("GET", "/memories"): {"memories": [MEMORY]},
    ("POST", "/graph/query"): GRAPH,
    ("GET", "/observations/locate"): {"sessions": {"obs_1": SESSION["id"]}},
}
