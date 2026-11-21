# backend/app/model3d/packs/building/build.py
"""building_from_spec: a building spec becomes part dicts (storey groups with floor, walls, openings, furniture, labels; roof)."""

import math
from typing import Any

from app.model3d.packs.building import furniture as fur
from app.model3d.packs.building.geom import bbox
from app.model3d.packs.building.openings import opening_parts, resolve
from app.model3d.packs.building.parts import box, group, text
from app.model3d.packs.building.roof import roof_parts
from app.model3d.packs.building.spec import FLOOR_THICKNESS, BuildingSpecError, normalize, num
from app.model3d.packs.building.walls import wall_list, wall_parts

KINDS = ("floor", "walls", "openings", "furniture", "labels")
LAYER_STEP = 10  # z_index spacing between storeys; kinds add 0..4 (roof sits above all storeys)


def layer_name(storey_id: str, kind: str) -> str:
    return f"{storey_id}.{kind}"


def building_from_spec(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Part dicts for the building. Each storey is a top-level group `storey-<id>` (layer `<id>`) at its elevation;
    kinds live on layers `<id>.floor|walls|openings|furniture|labels`; the roof is a top-level group `roof` (layer `roof`).
    Every part carries props.storey and props.kind. Raises BuildingSpecError on invalid specs."""
    s = normalize(spec)
    parts: list[dict[str, Any]] = []
    for si, st in enumerate(s["storeys"]):
        parts += _storey(st, si, s["wall_color"])
    if s["roof"]:
        top = max(st["elevation"] + st["height"] for st in s["storeys"])
        pts = [p for st in s["storeys"] for r in st["rooms"] for p in r["polygon"]]
        parts += roof_parts(s["roof"]["type"], bbox(pts), top, s["roof"]["overhang"], s["roof"]["color"], "roof",
                            {"storey": "roof", "kind": "roof"})
    ids = [p["id"] for p in parts]
    if len(set(ids)) != len(ids):
        raise BuildingSpecError("generated duplicate part ids; room, wall and opening ids must be unique per storey")
    return parts


def layer_defs(parts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Layer settings (z_index per storey and kind) for the layers used by `parts`, for Model.layers."""
    out: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for p in parts:
        sid = p["props"].get("storey")
        if sid and sid not in order:
            order.append(sid)
    for p in parts:
        sid, kind = p["props"].get("storey"), p["props"].get("kind")
        i = order.index(sid) if sid in order else 0
        z = LAYER_STEP * i + (KINDS.index(kind) if kind in KINDS else 0)
        out[p["layer"]] = {"z_index": LAYER_STEP * len(order) if sid == "roof" else z}
    return out


def _storey(st: dict[str, Any], si: int, wall_color: str | None = None) -> list[dict[str, Any]]:
    sid = st["id"]
    walls = wall_list(st)
    holes = resolve(st, walls)
    gid = f"storey-{sid}"
    base = {"storey": sid}
    out = [group(gid, st["name"], [0, st["elevation"], 0], sid, None, props={**base, "kind": "storey", "height": st["height"]})]
    for r in st["rooms"]:
        x0, y0, x1, y1 = bbox(r["polygon"])
        pr = {**base, "kind": "floor", "room": r["id"]}
        if r["is_rect"]:
            out.append(box(f"{sid}-floor-{r['id']}", f"floor {r['name']}", [(x0 + x1) / 2, -FLOOR_THICKNESS / 2, (y0 + y1) / 2],
                           [x1 - x0, FLOOR_THICKNESS, y1 - y0], layer_name(sid, "floor"), r["floor_color"], gid, props=pr))
        else:
            out.append({"id": f"{sid}-floor-{r['id']}", "kind": "extrude", "name": f"floor {r['name']}", "parent": gid,
                        "pos": [0, -FLOOR_THICKNESS, 0], "color": r["floor_color"], "layer": layer_name(sid, "floor"), "props": pr,
                        "geom": {"outline": r["polygon"], "height": FLOOR_THICKNESS, "floor": False}})
        out.append(text(f"{sid}-label-{r['id']}", r["name"], [(x0 + x1) / 2, 0.15, (y0 + y1) / 2], layer_name(sid, "labels"), gid)
                   | {"props": {**base, "kind": "labels", "room": r["id"]}})
    for w in walls:
        out += wall_parts(w, holes[w["id"]], f"{sid}-wall-{w['id']}", gid, layer_name(sid, "walls"), {**base, "kind": "walls"},
                           *([wall_color] if wall_color else []))
        for o in holes[w["id"]]:
            out += opening_parts(w, o, f"{sid}-{o['kind']}-{o['id']}", gid, layer_name(sid, "openings"), {**base, "kind": "openings"})
    for i, f in enumerate(st["furniture"]):
        out += _furniture(f, i, st, gid)
    return out


def _furniture(f: object, i: int, st: dict[str, Any], gid: str) -> list[dict[str, Any]]:
    what = f"furniture[{i}]"
    if not isinstance(f, dict) or f.get("kind") not in fur.DEFAULTS:
        raise BuildingSpecError(f"{what}.kind must be one of {sorted(fur.DEFAULTS)}")
    kind, sid = f["kind"], st["id"]
    size = f.get("size", fur.default_size(kind))
    if not (isinstance(size, (list, tuple)) and len(size) == 3):
        raise BuildingSpecError(f"{what}.size must be [width, depth, height] in metres")
    size = [num(v, what, 0.02) for v in size]
    room = next((r for r in st["rooms"] if r["id"] == f.get("room")), None)
    if f.get("room") and room is None:
        raise BuildingSpecError(f"{what}.room '{f['room']}' is not a room of storey '{sid}'")
    if "pos" in f:
        pos = [num(f["pos"][0], what), num(f["pos"][1], what)] if isinstance(f["pos"], (list, tuple)) and len(f["pos"]) == 2 else None
        if pos is None:
            raise BuildingSpecError(f"{what}.pos must be [x, y]")
    elif room:
        x0, y0, x1, y1 = bbox(room["polygon"])
        pos = [(x0 + x1) / 2, (y0 + y1) / 2]
    else:
        raise BuildingSpecError(f"{what} needs pos or room")
    yaw = -math.radians(num(f.get("rot", 0.0), what))  # rot: degrees clockwise in the plan; 0 faces plan +y
    pid = f"{sid}-furn-{i + 1}-{kind}"
    layer = layer_name(sid, "furniture")
    props = {"storey": sid, "kind": "furniture", "furniture": kind, **({"room": room["id"]} if room else {})}
    out = [group(pid, f.get("name") or kind, [pos[0], 0.0, pos[1]], layer, gid, [0.0, yaw, 0.0], props)]
    color = f.get("color") or fur.default_color(kind)
    for pc in fur.pieces(kind, size, color):
        out.append(box(f"{pid}-{pc['name']}", pc["name"], pc["pos"], pc["size"], layer, pc["color"], pid, props=props))
    return out
