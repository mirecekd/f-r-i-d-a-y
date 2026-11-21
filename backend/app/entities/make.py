# backend/app/entities/make.py
"""Create an `entity` scene object for a stored item and place it by the auto-layout."""

from typing import Any

from app.entities.layout import next_free_slot
from app.entities.shapes import accent_of
from app.scene import SceneStore
from app.scene_schema import SceneError

TITLE_CHARS = 60


def entity_id(ref_type: str, ref_id: str) -> str:
    return f"ent-{ref_type}-{ref_id[:8]}"


def taken_positions(scene: SceneStore) -> list[list[float]]:
    return [list(o["pos"]) for o in scene.objects() if o.get("pos") and o["kind"] != "link"]


async def add_entity(
    scene: SceneStore, emit: Any, ref_type: str, ref_id: str, shape: str, title: str,
    subtitle: str | None = None, thumb: str | None = None, pos: list[float] | None = None, scale: Any = None,
) -> dict[str, Any]:
    """Add (or replace) the entity of one stored item; returns {ok, object_id, pos} or {error}."""
    oid = entity_id(ref_type, ref_id)
    old = next((o for o in scene.objects() if o["id"] == oid), None)
    where = pos or (list(old["pos"]) if old and old.get("pos") else None) or next_free_slot(taken_positions(scene))
    obj: dict[str, Any] = {
        "id": oid, "kind": "entity", "shape": shape, "title": title[:TITLE_CHARS], "accent": accent_of(shape),
        "ref": {"type": ref_type, "id": ref_id}, "pos": where,
    }
    if subtitle:
        obj["subtitle"] = subtitle[:TITLE_CHARS]
    if thumb:
        obj["thumb"] = thumb
    if scale is not None:
        obj["scale"] = scale
    ops = [{"op": "add", "obj": obj}]
    try:
        scene.apply(ops)
    except SceneError as e:
        return {"error": str(e)}
    await emit({"t": "scene", "ops": ops})
    return {"ok": True, "object_id": oid, "pos": where}
