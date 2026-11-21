# backend/app/deck/tools.py
"""Model tools over the deck: deck_list, deck_get, deck_tag, deck_pin, deck_forget (approval), deck_open."""

import asyncio
from typing import Any

from app.deck import query, registry
from app.deck.items import DeckError, clean_tags
from app.deck.names import find_by_name
from app.deck.opener import Opener
from app.deck.session import DeckSession
from app.voice.tools import Tool, ToolRegistry

_ID = {"id": {"type": "string", "description": "deck id from deck_list (4+ char prefix works)"}}
_UNKNOWN = "unknown deck item; call deck_list"


def _brief(item: dict[str, Any]) -> dict[str, Any]:
    keys = ("id", "type", "title", "subtitle", "tags", "pinned", "source", "parent_ids", "updated_at", "size")
    return {k: item[k] for k in keys}


def register_deck_tools(registry_: ToolRegistry, session: DeckSession) -> None:
    """Add the deck tools to this connection's registry. `session.opener` opens items on this connection."""
    opener: Opener = session.opener

    async def deck_list(a: dict[str, Any]) -> dict[str, Any]:
        raw_limit = a.get("limit")
        limit = raw_limit if isinstance(raw_limit, int) else 20
        try:
            items = await asyncio.to_thread(query.list_items, a.get("type"), a.get("query"), None, None, limit, 0)
            total = await asyncio.to_thread(query.count_items, a.get("type"), a.get("query"))
        except DeckError as e:
            return {"error": str(e)}
        return {"items": [_brief(i) for i in items], "total": total, "stats": query.stats()}

    async def deck_find(a: dict[str, Any]) -> dict[str, Any]:
        kind = a.get("type")
        raw_limit = a.get("limit")
        try:
            hits = await asyncio.to_thread(find_by_name, str(a.get("query") or ""), [kind] if kind else None,
                                           raw_limit if isinstance(raw_limit, int) else 8)
        except DeckError as e:
            return {"error": str(e)}
        return {"matches": [{**_brief(h), "score": h["score"], "ref_id": h["ref_id"]} for h in hits], "count": len(hits)}

    async def deck_place(a: dict[str, Any]) -> dict[str, Any]:
        return await session.place(a.get("id"), a.get("pos"))

    async def deck_get(a: dict[str, Any]) -> dict[str, Any]:
        item = query.resolve(a.get("id"))
        return {"item": item} if item else {"error": _UNKNOWN}

    async def deck_tag(a: dict[str, Any]) -> dict[str, Any]:
        item = query.resolve(a.get("id"))
        if item is None:
            return {"error": _UNKNOWN}
        tags = a.get("tags")
        if not isinstance(tags, list):
            return {"error": "tags must be a list of strings"}
        done = await asyncio.to_thread(registry.update, item["id"], tags=clean_tags(tags))
        return {"ok": True, "id": done["id"], "tags": done["tags"]}

    async def deck_pin(a: dict[str, Any]) -> dict[str, Any]:
        item = query.resolve(a.get("id"))
        if item is None:
            return {"error": _UNKNOWN}
        done = await asyncio.to_thread(registry.update, item["id"], pinned=a.get("pinned") is not False)
        return {"ok": True, "id": done["id"], "pinned": done["pinned"]}

    async def deck_forget(a: dict[str, Any]) -> dict[str, Any]:
        item = query.resolve(a.get("id"))
        if item is None:
            return {"error": _UNKNOWN}
        await asyncio.to_thread(registry.delete, item["id"], False)
        return {"ok": True, "id": item["id"], "note": "removed from the deck only; the stored file or model is kept"}

    def forget_summary(a: dict[str, Any]) -> str:
        item = query.resolve(a.get("id"))
        return f"Remove '{item['title']}' from the deck (the stored data stays)" if item else "Remove an item from the deck"

    def tool(name: str, desc: str, props: dict[str, Any], required: list[str], fn: Any, **kw: Any) -> None:
        registry_.register(Tool(name, desc, {"type": "object", "properties": props, "required": required}, fn, **kw))

    tool("deck_list", "Browse the deck: everything the user saved or Friday created (images, files, 3D models, memory "
         "searches). Newest first, pinned first. Optional type (image|file|model3d|scene|note|view|memory_graph) and a "
         "text query.", {"type": {"type": "string"}, "query": {"type": "string"}, "limit": {"type": "integer"}}, [], deck_list)
    tool("deck_get", "Full details of one deck item (tags, provenance, meta).", _ID, ["id"], deck_get)
    tool("deck_tag", "Replace the tags of a deck item.", {**_ID, "tags": {"type": "array", "items": {"type": "string"}}},
         ["id", "tags"], deck_tag)
    tool("deck_pin", "Pin (default) or unpin a deck item so it stays first.", {**_ID, "pinned": {"type": "boolean"}},
         ["id"], deck_pin)
    tool("deck_forget", "Remove an item from the deck list only (the stored file or model is NOT deleted).", _ID, ["id"],
         deck_forget, risky=True, confirm_summary=forget_summary)
    tool("deck_find", "Find deck items by file NAME or title (case-insensitive, accents ignored, extension optional: "
         "'architect' finds 'architect.webp'). Use it when the user names a file; returns the best matches with ids.",
         {"query": {"type": "string"}, "type": {"type": "string"}, "limit": {"type": "integer"}}, ["query"], deck_find)
    tool("deck_place", "Put a deck item on the 3D desk as an entity tile (auto-layout, or pos [x,y,z]). An item that is "
         "already on the desk is only framed.", {**_ID, "pos": {"type": "array", "items": {"type": "number"}, "minItems": 3,
                                                               "maxItems": 3}}, ["id"], deck_place)
    tool("deck_open", "Open a deck item on the screen: image card, file tile, 3D model, memory graph.", _ID, ["id"],
         opener.open_by_args)
