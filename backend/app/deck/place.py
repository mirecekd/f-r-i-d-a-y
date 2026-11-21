# backend/app/deck/place.py
"""deck_place: put a deck item on the 3D desk as an entity, through the same path as show_in_scene / file_to_scene."""

from typing import Any

from app.entities.make import add_entity, entity_id
from app.files import card as file_card
from app.files import store as file_store
from app.scene_schema import SceneError
from app.tools_friday.ctx import Ctx
from app.vision import store as image_store
from app.webpages import card as web_card
from app.webpages import store as web_store

CAMERA_BACK, CAMERA_UP = 9.0, 3.0


def entity_spec(item: dict[str, Any]) -> dict[str, Any]:
    """add_entity arguments of a deck item; DeckError-free: returns {'error'} for items that cannot stand on the desk."""
    kind, ref = item["type"], item["ref_id"]
    if kind == "image":
        meta = image_store.resolve(ref)
        return image_store.entity_args(meta) if meta else {"error": "the stored image is gone"}
    if kind == "file":
        meta = file_store.resolve(ref)
        return file_card.entity_args(meta) if meta else {"error": "the stored file is gone"}
    if kind == "web":
        page = web_store.resolve(ref)
        return web_card.entity_args(page) if page else {"error": "the stored page is gone"}
    if kind == "model3d":
        return {
            "ref_type": "model",
            "ref_id": ref,
            "shape": "model",
            "title": item["title"],
            "subtitle": item["subtitle"],
        }
    if kind == "workshop":
        return {"ref_type": "workshop", "ref_id": ref, "shape": "workshop", "title": f"Dilna: {item['title']}",
                "subtitle": item["subtitle"]}
    if kind == "memory_graph":
        return {
            "ref_type": "memory",
            "ref_id": ref,
            "shape": "note",
            "title": item["title"],
            "subtitle": item["subtitle"],
        }
    return {"error": f"items of type '{kind}' cannot be placed on the desk"}


def frame_op(pos: list[float]) -> dict[str, Any]:
    return {"op": "camera", "pos": [pos[0], pos[1] + CAMERA_UP, pos[2] + CAMERA_BACK], "look": list(pos)}


async def place_item(ctx: Ctx, item: dict[str, Any], pos: Any = None) -> dict[str, Any]:
    """Returns {ok, id, object_id, pos, already_on_desk}. An item already on the desk is only framed, never duplicated."""
    spec = entity_spec(item)
    if "error" in spec:
        return spec
    oid = entity_id(spec["ref_type"], spec["ref_id"])
    old = next((o for o in ctx.scene.objects() if o["id"] == oid), None)
    if old is not None and old.get("pos"):
        op = frame_op(old["pos"])
        try:
            ctx.scene.apply([op])
        except SceneError as e:
            return {"error": str(e)}
        await ctx.emit({"t": "scene", "ops": [op]})
        return {"ok": True, "id": item["id"], "object_id": oid, "pos": old["pos"], "already_on_desk": True}
    result = await add_entity(ctx.scene, ctx.emit, **spec, pos=pos)
    if "error" in result:
        return result
    return {
        "ok": True,
        "id": item["id"],
        "object_id": result["object_id"],
        "pos": result["pos"],
        "already_on_desk": False,
    }
