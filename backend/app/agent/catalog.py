# backend/app/agent/catalog.py
"""Model catalog per role, cached for 10 minutes.

Entries are {id, provider: 'gemini'|'litellm', label, group, roles: ['chat'|'agent'], caps?: {tools, vision, reasoning}}.
Role `chat` = Gemini Live models only; role `agent` = LiteLLM chat models plus Gemini text models.
"""

import logging
import os
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from google import genai

from app.agent import catalog_gemini as gemini
from app.agent import catalog_litellm as litellm

log = logging.getLogger("friday.agent.catalog")

TTL_SECONDS = 600

Entry = dict[str, Any]
Fetcher = Callable[[], Awaitable[list[Entry]]]


async def fetch_litellm(client: httpx.AsyncClient | None = None) -> list[Entry]:
    """Prefer /model/info (capability flags); fall back to /models when the key may not read it."""
    base, key = os.getenv("LITELLM_BASE_URL"), os.getenv("LITELLM_API_KEY")
    if not base or not key:
        return []
    own = client or httpx.AsyncClient(timeout=20)
    headers = {"Authorization": f"Bearer {key}"}
    try:
        resp = await own.get(base.rstrip("/") + "/model/info", headers=headers)
        if resp.is_success:
            return litellm.filter_model_info(resp.json())
        log.info("litellm /model/info answered %s, falling back to /models", resp.status_code)
        resp = await own.get(base.rstrip("/") + "/models", headers=headers)
        resp.raise_for_status()
        return litellm.filter_models(resp.json())
    finally:
        if client is None:
            await own.aclose()


async def fetch_gemini(client: Any = None) -> list[Entry]:
    key = os.getenv("GEMINI_API_KEY")
    if client is None:
        if not key:
            return []
        client = genai.Client(api_key=key)
    models = [m async for m in await client.aio.models.list()]
    return gemini.filter_live(models) + gemini.filter_text(models)


class CatalogCache:
    """Per-provider cache: a provider that failed is retried on the next call, not cached."""

    def __init__(self, fetchers: dict[str, Fetcher] | None = None, ttl: float = TTL_SECONDS, clock=time.monotonic):
        self.fetchers = fetchers or {"gemini": fetch_gemini, "litellm": fetch_litellm}
        self.ttl = ttl
        self.clock = clock
        self._entries: dict[str, tuple[float, list[Entry]]] = {}

    async def get(self) -> list[Entry]:
        now = self.clock()
        for provider, fetch in self.fetchers.items():
            cached = self._entries.get(provider)
            if cached and now - cached[0] < self.ttl:
                continue
            try:
                self._entries[provider] = (now, await fetch())
            except Exception as e:
                log.warning("catalog fetch for %s failed: %s", provider, type(e).__name__)
        return [e for _, entries in self._entries.values() for e in entries]

    def provider_of(self, model_id: str) -> str | None:
        for _, entries in self._entries.values():
            for e in entries:
                if e["id"] == model_id:
                    return e["provider"]
        return None

    def has_role(self, model_id: str, role: str) -> bool:
        return any(e["id"] == model_id and role in e["roles"] for _, es in self._entries.values() for e in es)


catalog = CatalogCache()
