# backend/app/entities/messages.py
"""Browser messages about entities: entity_open (card), entity_link (link mode) and entity_remove (delete from the deck)."""

from typing import Any

from app.entities.links import links_of, make_link
from app.entities.open import find_entity, open_card
from app.scene_schema import SceneError

KINDS = frozenset({"entity_open", "entity_link", "entity_remove"})


async def handle_entity_message(emit: Any, agent: Any, msg: dict[str, Any]) -> None:
    """Handle one of KINDS; errors go to the chat. `entity_remove` deletes the scene object and its links, never the stored item."""
    ctx, kind = agent.vision.ctx, msg.get("t")
    ops: list[dict[str, Any]] = []
    try:
        if kind == "entity_open":
            result = await open_card(ctx, agent.vision, agent.files, msg.get("id"))
            if "error" in result:
                raise SceneError(result["error"])
        elif kind == "entity_link":
            ops, _ = make_link(ctx.scene, str(msg.get("from")), str(msg.get("to")), None, None)
        elif find_entity(ctx, msg.get("id")) is None:
            raise SceneError("unknown entity id")
        else:
            eid = str(msg["id"])
            ops = [{"op": "del", "id": k["id"]} for k in links_of(ctx.scene, eid)] + [{"op": "del", "id": eid}]
        if ops:
            ctx.scene.apply(ops)
            await emit({"t": "scene", "ops": ops})
    except SceneError as e:
        await emit({"t": "error", "message": f"{kind}: {e}"})
