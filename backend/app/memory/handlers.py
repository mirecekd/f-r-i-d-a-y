# backend/app/memory/handlers.py
"""Handlers for browser messages that concern memory (not model tools)."""

from collections.abc import Awaitable, Callable
from typing import Any

from app.deck import hooks as deck_hooks
from app.memory import client, focus, graph
from app.views import view_msg

GRAPH_VIEW_TITLE = "Memory graph"
LOADING_TEXT = "Nacitam pamet..."
SEARCHING_TEXT = "Hledam v pameti..."

Send = Callable[[dict[str, Any]], Awaitable[None]]


def _text(msg: dict[str, Any], key: str) -> str | None:
    value = msg.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


async def show_memory_graph(send: Send, msg: dict[str, Any]) -> None:
    """`show_memory_graph` message: notice first (the first build takes seconds), then the memory_graph view."""
    await send({"t": "notice", "text": LOADING_TEXT})
    try:
        data = await graph.memory_graph(_text(msg, "project"), _text(msg, "query"))
    except client.MemoryUnavailable as e:
        await send({"t": "error", "message": str(e)})
        return
    await send(view_msg("memory_graph", data, GRAPH_VIEW_TITLE))


async def memory_search(send: Send, msg: dict) -> None:
    """`memory_search` message: notice, then the query-focused memory_graph view (highlight, hits, summary)."""
    query = _text(msg, "query")
    if not query:
        await send({"t": "error", "message": "memory_search needs a non-empty query"})
        return
    await send({"t": "notice", "text": SEARCHING_TEXT})
    try:
        data = await focus.focused_graph(query, _text(msg, "project"))
    except client.MemoryUnavailable as e:
        await send({"t": "error", "message": str(e)})
        return
    deck_hooks.memory_search_done(query, _text(msg, "project"), data)
    await send(view_msg("memory_graph", data, GRAPH_VIEW_TITLE))
