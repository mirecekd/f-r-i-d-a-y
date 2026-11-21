# backend/app/memory/fetch.py
"""Read-only fetch helpers over the agentmemory endpoints shared by the digest, recall and graph."""

import asyncio
from datetime import datetime

from app.memory import client

DAY_S = 86400
SESSION_PAGE = 100
OBS_LIMIT = 500


def parse_ts(value: object) -> float:
    """ISO-8601 string to epoch seconds; 0.0 when missing or malformed."""
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


async def recent_sessions(since: float, max_pages: int = 3) -> list[dict]:
    """Sessions updated after `since` (epoch s), newest first; pages /sessions by cursor."""
    found: list[dict] = []
    cursor = None
    for _ in range(max_pages):
        data = await client.get("/sessions", limit=SESSION_PAGE, cursor=cursor)
        page = data.get("sessions") or []
        found += [s for s in page if parse_ts(s.get("updatedAt") or s.get("startedAt")) >= since]
        cursor = data.get("nextCursor")
        if not cursor or not page or parse_ts(page[-1].get("startedAt")) < since - DAY_S:
            break
    return found


async def session_observations(session_id: str) -> list[dict]:
    data = await client.get("/observations", sessionId=session_id, limit=OBS_LIMIT)
    return data.get("observations") or []


async def recent_memories(limit: int = 100) -> list[dict]:
    data = await client.get("/memories", limit=limit)
    return data.get("memories") or []


async def gather_limited(coros: list, width: int = 8) -> list:
    """Run coroutines with bounded concurrency; a failed one yields None instead of raising."""
    sem = asyncio.Semaphore(width)

    async def one(coro):
        async with sem:
            try:
                return await coro
            except client.MemoryUnavailable:
                return None

    return await asyncio.gather(*(one(c) for c in coros))
