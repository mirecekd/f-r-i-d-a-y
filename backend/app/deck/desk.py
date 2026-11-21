# backend/app/deck/desk.py
"""The shared 3D desk as seen from outside a WebSocket: POST /api/upload puts a new file on it for every open connection."""

import logging
from typing import Any

from app.entities.make import add_entity
from app.tools_friday.ctx import Ctx

log = logging.getLogger("friday.deck")
_ctxs: list[Ctx] = []


def attach(ctx: Ctx) -> None:
    if ctx not in _ctxs:
        _ctxs.append(ctx)


def detach(ctx: Ctx) -> None:
    if ctx in _ctxs:
        _ctxs.remove(ctx)


async def announce_and_place(ready: dict[str, Any], entity: dict[str, Any]) -> dict[str, Any] | None:
    """Tell every connection about the upload (`ready` = file_ready/image_ready), THEN add its entity to the scene.

    `entity` holds add_entity arguments (ref_type, ref_id, shape, title, ...). Without a connection nothing happens
    and None is returned: the item is still in the deck and can be placed later."""
    if not _ctxs:
        return None
    scene = _ctxs[0].scene
    targets = [c for c in _ctxs if c.scene is scene]

    async def fan_out(msg: dict[str, Any]) -> None:
        for ctx in targets:
            try:
                await ctx.emit(msg)
            except Exception as e:  # one dead connection must not block the others
                log.debug("deck: connection dropped while announcing: %s", e)

    await fan_out(ready)
    return await add_entity(scene, fan_out, **entity)
