# backend/app/workshop/sources_tools.py
"""Model tool `workshop_sources`: read, add and remove the reference material around the table."""

from collections.abc import Callable
from typing import Any

from app.workshop import sources, store
from app.workshop.session import WorkshopSession

IDS = {"type": "array", "items": {"type": "string"}}
DESCRIPTION = (
    "Reference material around the table of the open workshop (deck items: images, files, models, pages). "
    "add / remove take deck ids (from deck_list or deck_find); at most 12 sources. Always returns the current "
    "sources [{deck_id, entity_id, title, kind, summary}] so you can read what stands around the table."
)


def register_sources_tool(add: Callable[..., None], session: WorkshopSession) -> None:
    """Register `workshop_sources` through the registration helper `add` of tools.py."""

    async def workshop_sources(a: dict[str, Any]) -> dict[str, Any]:
        rec = session.require()
        notes = sources.drop_dead(rec)
        if a.get("remove") is not None:
            sources.remove(rec, a.get("remove"))
        if a.get("add") is not None:
            sources.add(rec, a.get("add"))
        store.save(rec)
        await sources.place(session.ctx, rec)
        return {"ok": True, "sources": sources.describe(rec), "notes": notes}

    add("workshop_sources", DESCRIPTION, {"add": IDS, "remove": IDS}, [], workshop_sources)
