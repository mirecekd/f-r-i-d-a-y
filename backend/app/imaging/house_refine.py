# backend/app/imaging/house_refine.py
"""Turn inside-photo observations into model change proposals (no regeneration, stable ids)."""

from typing import Any

from app.imaging.colors import to_hex
from app.model3d.model import Model
from app.model3d.packs.building import furniture as fur
from app.model3d.packs.building.geom import bbox
from app.model3d.packs.building.parts import box, group


def room_names(model: Model) -> dict[str, str]:
    """{room id: room name} from the floor parts of a building model."""
    return {p.props["room"]: p.name.removeprefix("floor ") for p in model.parts.values()
            if p.props.get("kind") == "floor" and p.props.get("room")}


def _floor_part(model: Model, room_id: str) -> Any:
    return next((p for p in model.parts.values() if p.props.get("kind") == "floor" and p.props.get("room") == room_id), None)


def match_room(model: Model, label: str) -> str | None:
    """Room id for a model-given label that may be an id or a name."""
    names = room_names(model)
    low = label.strip().lower()
    return next((rid for rid, name in names.items() if low in (rid.lower(), name.lower())), None)


def _furniture_parts(model: Model, room_id: str, kind: str, count: int) -> list[dict[str, Any]]:
    floor = _floor_part(model, room_id)
    sid = floor.props["storey"]
    x, z = floor.pos[0], floor.pos[2]
    pid = f"{sid}-furn-p{count + 1}-{kind}"
    layer = f"{sid}.furniture"
    props = {"storey": sid, "kind": "furniture", "furniture": kind, "room": room_id}
    out = [group(pid, kind, [x, 0.0, z], layer, floor.parent, None, props)]
    out += [box(f"{pid}-{pc['name']}", pc["name"], pc["pos"], pc["size"], layer, pc["color"], pid, props=props)
            for pc in fur.pieces(kind, fur.default_size(kind), fur.default_color(kind))]
    return out


def changes_from(model: Model, analysis: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """(changes for model_propose, notes about observations that matched nothing)."""
    changes: list[dict[str, Any]] = []
    skipped: list[str] = []
    added: dict[tuple[str, str], int] = {}
    for obs in analysis["observations"]:
        rid = match_room(model, obs["room"])
        floor = _floor_part(model, rid) if rid else None
        if rid is None or floor is None:
            skipped.append(f"no modelled room matches '{obs['room']}'")
            continue
        color = to_hex(obs["floor_color"] or obs["floor_material"])
        if color and color != (floor.color or "").lower():
            changes.append({"op": "edit", "id": floor.id, "props": {"color": color}})
        have = {p.props.get("furniture") for p in model.parts.values() if p.props.get("room") == rid and p.props.get("kind") == "furniture"}
        for kind in obs["furniture"]:
            if kind in fur.DEFAULTS and kind not in have and (rid, kind) not in added:
                added[(rid, kind)] = len(added)
                changes += [{"op": "add", "part": p} for p in _furniture_parts(model, rid, kind, len(added))]
    return changes, skipped


def footprint(model: Model) -> tuple[float, float, float, float] | None:
    pts = [[p.pos[0], p.pos[2]] for p in model.parts.values() if p.props.get("kind") == "floor"]
    return bbox(pts) if pts else None
