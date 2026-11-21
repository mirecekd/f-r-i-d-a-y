# backend/app/vision/capability.py
"""Which model sees images: the pinned agent model if vision-capable, else gemini-flash-latest."""

import logging
import os
import time

import httpx

from app.agent.catalog import catalog

log = logging.getLogger("friday.vision")
FALLBACK_MODEL = "gemini-flash-latest"
_TTL = 600.0
_vision_ids: tuple[float, set[str]] | None = None


async def _litellm_vision_ids() -> set[str]:
    """LiteLLM model ids whose /model/info says supports_vision; cached 10 minutes, empty on failure."""
    global _vision_ids
    if _vision_ids and time.monotonic() - _vision_ids[0] < _TTL:
        return _vision_ids[1]
    base, key = os.getenv("LITELLM_BASE_URL"), os.getenv("LITELLM_API_KEY")
    ids: set[str] = set()
    if base and key:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(base.rstrip("/") + "/model/info", headers={"Authorization": f"Bearer {key}"})
                resp.raise_for_status()
            ids = {
                str(m["model_name"]) for m in resp.json().get("data", []) if (m.get("model_info") or {}).get("supports_vision")
            }
        except Exception as e:
            log.warning("vision capability lookup failed: %s", type(e).__name__)
            return set()
    _vision_ids = (time.monotonic(), ids)
    return ids


async def is_vision_capable(model: str) -> bool:
    provider = catalog.provider_of(model)
    if provider is None:
        await catalog.get()
        provider = catalog.provider_of(model)
    if provider == "gemini":
        return True
    return provider == "litellm" and model in await _litellm_vision_ids()


async def pick_vision_model(pinned: str) -> str:
    return pinned if await is_vision_capable(pinned) else FALLBACK_MODEL
