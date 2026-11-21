# backend/app/model3d/packs/building/scale.py
"""Rescale a building spec so one room gets a stated width (the user says 'this room is 4 m wide')."""

import math
from typing import Any

from app.model3d.packs.building.geom import bbox, edges
from app.model3d.packs.building.openings import KINDS, edge_index
from app.model3d.packs.building.spec import BuildingSpecError, normalize
from app.model3d.packs.building.walls import wall_list


def building_scale_to_room(spec: dict[str, Any], room_id: str, width_m: float) -> dict[str, Any]:
    """New normalised spec whose plan is scaled uniformly (about the origin) so room `room_id` is `width_m` wide in x.

    Wall lengths, room sizes and furniture positions scale; heights, thicknesses, furniture sizes and opening
    widths stay in real metres (a door stays a door). Opening offsets scale and are clamped to fit their wall or edge.
    """
    if isinstance(width_m, bool) or not isinstance(width_m, (int, float)) or not math.isfinite(width_m) or width_m <= 0:
        raise BuildingSpecError("width_m must be a positive number")
    s = normalize(spec)
    room = next((r for st in s["storeys"] for r in st["rooms"] if r["id"] == room_id), None)
    if room is None:
        ids = [r["id"] for st in s["storeys"] for r in st["rooms"]]
        raise BuildingSpecError(f"unknown room '{room_id}'; rooms: {ids}")
    x0, _, x1, _ = bbox(room["polygon"])
    k = width_m / (x1 - x0)
    for st in s["storeys"]:
        for r in st["rooms"]:
            r["polygon"] = [_scale(p, k) for p in r["polygon"]]
        for w in st["walls"]:
            w["a"], w["b"] = _scale(w["a"], k), _scale(w["b"], k)
        for f in st["furniture"]:
            if "pos" in f:
                f["pos"] = _scale(f["pos"], k)
        _fit_openings(st, k)
    return s


def _fit_openings(st: dict[str, Any], k: float) -> None:
    walls = {w["id"]: w["length"] for w in wall_list(st)}
    rooms = {r["id"]: edges(r["polygon"]) for r in st["rooms"]}
    for o in st["openings"]:
        if "wall" in o:
            limit = walls.get(o["wall"])
        else:
            edge = edge_index(o)
            ring = rooms.get(o.get("room"), [])
            limit = math.dist(*ring[edge]) if isinstance(edge, int) and 0 <= edge < len(ring) else None
        if limit is None:
            continue
        width = min(o.get("width", KINDS.get(o.get("kind"), {}).get("width", 0.9)), max(limit - 0.1, 0.1))
        o["width"] = _floor3(width)
        o["offset"] = _floor3(max(0.0, min(o.get("offset", 0.0) * k, limit - o["width"])))


def _floor3(v: float) -> float:
    """Round down to millimetres so offset + width never exceeds the wall length."""
    return math.floor(v * 1000 + 1e-6) / 1000


def _scale(p: list[float], k: float) -> list[float]:
    return [round(p[0] * k, 4), round(p[1] * k, 4)]
