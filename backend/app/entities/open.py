# backend/app/entities/open.py
"""Open the readable 2D card (image_card / file_card) of an entity's stored item."""

from typing import Any

from app.files import store as file_store
from app.files.service import FileService
from app.tools_friday.ctx import Ctx
from app.views import ViewError, view_msg
from app.vision import store as image_store
from app.vision.service import VisionService, card_data
from app.webpages import card as web_card
from app.webpages import store as web_store


def find_entity(ctx: Ctx, entity_id: object) -> dict[str, Any] | None:
    return next((o for o in ctx.scene.objects() if o["id"] == entity_id and o["kind"] == "entity"), None)


async def open_card(ctx: Ctx, vision: VisionService, files: FileService, entity_id: object) -> dict[str, Any]:
    """Emit the card of the stored item the entity refers to; returns {ok} or {error}."""
    obj = find_entity(ctx, entity_id)
    if obj is None:
        return {"error": "unknown entity id; call entity_list"}
    ref = obj.get("ref")
    if not ref:
        return {"error": "this entity has no stored item to open"}
    return await open_ref(ctx, vision, files, ref)


async def open_ref(ctx: Ctx, vision: VisionService, files: FileService, ref: dict[str, Any]) -> dict[str, Any]:
    """Emit the card of the stored item `ref` = {type, id}; shared by entity_open and the deck."""
    if ref["type"] == "file":
        meta = file_store.resolve(ref["id"])
        return {"error": "the stored file no longer exists"} if meta is None else await files.show_card(meta)
    if ref["type"] == "image":
        img = image_store.resolve(ref["id"])
        if img is None:
            return {"error": "the stored image no longer exists"}
        if not img.get("analysis"):
            await vision.analyze(img)  # emits the image_card once the analysis is done
            return {"ok": True}
        try:
            msg = view_msg("image_card", card_data(img, img["analysis"]), img["name"], f"image-{img['id'][:8]}")
        except ViewError as e:
            return {"error": f"cannot show the image card: {e}"[:200]}
        await ctx.emit(msg)
        return {"ok": True, "view_id": msg["id"]}
    if ref["type"] == "web":
        page = web_store.resolve(ref["id"])
        if page is None:
            return {"error": "the stored page no longer exists"}
        try:
            msg = view_msg("file_card", web_card.card_data(page, web_store.text_of(page["id"])), page["title"], f"web-{page['id'][:8]}")
        except (ViewError, OSError) as e:
            return {"error": f"cannot show the page card: {e}"[:200]}
        await ctx.emit(msg)
        return {"ok": True, "view_id": msg["id"]}
    if ref["type"] == "workshop":
        from app.workshop.deck_hooks import enter_for

        return await enter_for(ctx, ref["id"])  # no card: the camera glides to the work table
    return {"error": f"no card for {ref['type']} items"}
