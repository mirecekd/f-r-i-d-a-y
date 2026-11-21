# backend/app/memory/warm.py
"""Warm the generic memory graph cache at server start so the first show_memory_graph is instant."""

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.memory import graph

log = logging.getLogger("friday.memory")


async def warm() -> None:
    """Build the graph once; any failure is only logged (the first real request retries)."""
    try:
        await graph.cached_graph()
        log.info("memory graph cache warmed")
    except Exception as e:  # noqa: BLE001 - warming is best effort and must never break startup
        log.info("memory graph warm-up skipped: %s", type(e).__name__)


@asynccontextmanager
async def lifespan(_app: object) -> AsyncIterator[None]:
    """FastAPI lifespan: start the warm-up in the background without delaying startup."""
    task = asyncio.create_task(warm()) if os.getenv("AGENTMEMORY_URL") else None
    yield
    if task:
        task.cancel()
