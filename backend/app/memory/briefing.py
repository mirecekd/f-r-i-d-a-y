# backend/app/memory/briefing.py
"""Short session-start briefing for the voice system prompt."""

import asyncio
import logging

from app.memory import awareness, client

log = logging.getLogger("friday.memory")
MAX_CHARS = 600
BRIEFING_TIMEOUT_S = 4.0
DECISION_CHARS = 95


async def startup_context() -> str:
    """Last 5 decisions plus the digest headline in at most 600 chars; "" when memory is unreachable."""
    try:
        head, _ = await awareness.headline()
        decisions = await awareness.recent_decisions(5)
    except client.MemoryUnavailable as e:
        log.info("startup briefing skipped: %s", e)
        return ""
    lines = [head] + [f"- {awareness.clip(d, DECISION_CHARS)}" for d in decisions]
    return awareness.clip_block("\n".join(lines), MAX_CHARS)


async def briefing_or_empty() -> str:
    """startup_context() bounded to a few seconds; any failure means no briefing, never an error."""
    try:
        return await asyncio.wait_for(startup_context(), BRIEFING_TIMEOUT_S)
    except Exception as e:  # the voice session must start even when memory is down
        log.info("startup briefing skipped: %s", type(e).__name__)
        return ""
