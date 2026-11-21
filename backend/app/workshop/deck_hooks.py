# backend/app/workshop/deck_hooks.py
"""Deck and desk side of a workshop: the `workshop` deck item, the desk tile, name lookup and entering by reference."""

import logging
from typing import Any

from app.deck import names, query, registry
from app.deck.items import DeckError
from app.entities.make import add_entity, entity_id
from app.tools_friday.ctx import Ctx
from app.workshop import store

log = logging.getLogger("friday.workshop")
_sessions: dict[int, Any] = {}  # id(ctx) -> WorkshopSession of that connection


def attach(ctx: Ctx, session: Any) -> None:
    _sessions[id(ctx)] = session


def detach(ctx: Ctx) -> None:
    _sessions.pop(id(ctx), None)


async def enter_for(ctx: Ctx, workshop_id: str) -> dict[str, Any]:
    """Enter the workshop `workshop_id` on this connection (entity_open, deck_open); {ok, id} or {error}."""
    session = _sessions.get(id(ctx))
    if session is None:
        return {"error": "the workshop is not available on this connection"}
    try:
        return await session.open(workshop_id)
    except store.WorkshopError as e:
        return {"error": str(e)}


def resolve(ref: object) -> str | None:
    """The workshop id a workshop id, deck id, entity id or title means; None when nothing (or nothing unique) matches."""
    text = str(ref or "").strip()
    if store.exists(text):
        return text
    if text.startswith("ent-workshop-"):
        prefix = text[len("ent-workshop-") :]
        hits = [w for w in store.list_ids() if w.startswith(prefix)] if len(prefix) >= 4 else []
        return hits[0] if len(hits) == 1 else None
    item = query.resolve(text)
    if item is not None and item["type"] == "workshop":
        return item["ref_id"]
    try:
        ref_id, _ = names.resolve_name(text, "workshop")
    except DeckError:
        return None
    return ref_id


def spec_text(rec: dict[str, Any]) -> str:
    """Words of the spec for full text search: the object name and the part ids and names."""
    spec = rec.get("spec") or {}
    words = [str(spec.get("name") or "")]
    for part in spec.get("parts") or []:
        if isinstance(part, dict):
            words += [str(part.get("id") or ""), str(part.get("name") or "")]
    return " ".join(w for w in words if w)[:4000]


def register_item(rec: dict[str, Any], parts: int, params: int) -> None:
    """Add or refresh the deck item of this workshop. Never raises: the deck must not break a build."""
    try:
        registry.register(
            "workshop",
            rec["id"],
            rec["title"],
            f"{parts} parts, {params} params",
            size=parts,
            source="generated",
            text=spec_text(rec),
            created_at=int(rec["created"]),
            meta={"parts": parts, "params": params, "sources": 0},
        )
    except Exception as e:
        log.warning("deck registration of workshop %s failed: %s: %s", rec["id"], type(e).__name__, e)


def forget_item(workshop_id: str) -> None:
    from app.deck.items import item_id

    try:
        registry.delete(item_id("workshop", workshop_id))
    except Exception as e:
        log.warning("deck removal of workshop %s failed: %s: %s", workshop_id, type(e).__name__, e)


async def put_on_desk(ctx: Ctx, rec: dict[str, Any], only_if_present: bool = False) -> None:
    """Show the desk tile `Dilna: <title>` (shape workshop, ref {type:'workshop', id}). `only_if_present` only renames an existing one."""
    present = any(o["id"] == entity_id("workshop", rec["id"]) for o in ctx.scene.objects())
    if only_if_present and not present:
        return
    result = await add_entity(ctx.scene, ctx.emit, "workshop", rec["id"], "workshop", f"Dilna: {rec['title']}")
    if "error" in result:
        log.warning("desk tile of workshop %s failed: %s", rec["id"], result["error"])
