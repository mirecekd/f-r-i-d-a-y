# backend/app/memory/client.py
"""Async client for the agentmemory REST API; failures become {"error": ...} payloads."""

import os
from typing import Any

import httpx

TIMEOUT_S = 10.0
_transport: httpx.AsyncBaseTransport | None = None  # tests inject an httpx.MockTransport


class MemoryUnavailable(Exception):
    """agentmemory is unconfigured, unreachable or answered with an error."""


async def request(method: str, path: str, params: dict[str, Any] | None = None, body: Any = None) -> dict:
    """One call under /agentmemory; never raises, errors come back as {"error": str} (no secrets in it)."""
    base = os.getenv("AGENTMEMORY_URL", "").rstrip("/")
    if not base:
        return {"error": "agentmemory is not configured (AGENTMEMORY_URL)"}
    secret = os.getenv("AGENTMEMORY_SECRET", "")
    headers = {"Authorization": f"Bearer {secret}"} if secret else {}
    query = {k: v for k, v in (params or {}).items() if v is not None}
    try:
        async with httpx.AsyncClient(transport=_transport, timeout=TIMEOUT_S) as http:
            resp = await http.request(method, f"{base}/agentmemory{path}", params=query, json=body, headers=headers)
    except httpx.HTTPError as e:
        return {"error": f"agentmemory unreachable: {type(e).__name__}"}
    try:
        data = resp.json()
    except ValueError:
        data = None
    if resp.status_code >= 400:
        detail = data.get("error") if isinstance(data, dict) and isinstance(data.get("error"), str) else ""
        return {"error": f"agentmemory HTTP {resp.status_code} {detail}"[:200]}
    return data if isinstance(data, dict) else {"error": "agentmemory returned a non-object response"}


async def _checked(method: str, path: str, params: dict[str, Any] | None, body: Any) -> dict:
    data = await request(method, path, params, body)
    if "error" in data:
        raise MemoryUnavailable(data["error"])
    return data


async def get(path: str, **params: Any) -> dict:
    """GET that raises MemoryUnavailable on failure; None params are dropped."""
    return await _checked("GET", path, params, None)


async def post(path: str, body: dict[str, Any]) -> dict:
    """POST (JSON body) that raises MemoryUnavailable on failure."""
    return await _checked("POST", path, None, body)
