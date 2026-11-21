# backend/app/model3d/packs/building/spec.py
"""Validate and normalise a building spec: rooms get polygons, storeys get elevations, defaults are filled."""

import copy
import math
import re
import unicodedata
from typing import Any

from app.model3d.packs.building.geom import area, bbox, rect_poly

STOREY_HEIGHT = 2.7
WALL_THICKNESS = 0.2
FLOOR_THICKNESS = 0.1
FURNITURE_KINDS = ("bed", "sofa", "table", "chair", "wardrobe", "desk", "kitchen_unit", "generic")
ROOF_TYPES = ("flat", "gable")


class BuildingSpecError(ValueError):
    """A building spec that cannot be turned into parts."""


def slug(text: str, fallback: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")[:32] or fallback


def num(v: object, what: str, low: float | None = None) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or abs(v) > 1e6:
        raise BuildingSpecError(f"{what} must be a finite number, got {v!r}")
    if low is not None and v < low:
        raise BuildingSpecError(f"{what} must be >= {low}, got {v}")
    return float(v)


def point(v: object, what: str) -> list[float]:
    if not (isinstance(v, (list, tuple)) and len(v) == 2):
        raise BuildingSpecError(f"{what} must be [x, y]")
    return [num(v[0], what), num(v[1], what)]


def normalize(spec: object) -> dict[str, Any]:
    """Return a deep copy of `spec` with defaults filled in; raise BuildingSpecError on anything invalid."""
    if not isinstance(spec, dict):
        raise BuildingSpecError("spec must be an object")
    if spec.get("units", "m") != "m":
        raise BuildingSpecError("only units 'm' is supported")
    raw = spec.get("storeys")
    if not isinstance(raw, list) or not raw:
        raise BuildingSpecError("spec.storeys must be a non-empty list")
    out: dict[str, Any] = {"name": str(spec.get("name", "building")), "units": "m", "storeys": [],
                           "roof": _roof(spec.get("roof")), "wall_color": _color(spec.get("wall_color"), "wall_color")}
    room_ids: set[str] = set()
    sids: set[str] = set()
    elevation = 0.0
    for i, st in enumerate(raw):
        if not isinstance(st, dict):
            raise BuildingSpecError(f"storeys[{i}] must be an object")
        sid = slug(st.get("name", ""), f"s{i}")
        if sid in sids:
            raise BuildingSpecError(f"duplicate storey name '{sid}'")
        sids.add(sid)
        height = num(st.get("height", STOREY_HEIGHT), f"storeys[{i}].height", 0.5)
        elevation = num(st["elevation"], f"storeys[{i}].elevation") if "elevation" in st else elevation
        rooms = [_room(r, f"storeys[{i}].rooms[{j}]", room_ids) for j, r in enumerate(st.get("rooms") or [])]
        if not rooms:
            raise BuildingSpecError(f"storeys[{i}] needs at least one room")
        walls = [_wall(w, f"storeys[{i}].walls[{j}]", height) for j, w in enumerate(st.get("walls") or [])]
        out["storeys"].append({
            "id": sid, "name": str(st.get("name", sid)), "elevation": elevation, "height": height, "rooms": rooms,
            "walls": walls, "openings": copy.deepcopy(st.get("openings") or []),
            "furniture": copy.deepcopy(st.get("furniture") or [])})
        elevation += height
    return out


def _room(r: object, what: str, ids: set[str]) -> dict[str, Any]:
    if not isinstance(r, dict):
        raise BuildingSpecError(f"{what} must be an object")
    if "polygon" in r:
        poly = [point(p, f"{what}.polygon") for p in r["polygon"]] if isinstance(r["polygon"], list) else []
        if len(poly) < 3:
            raise BuildingSpecError(f"{what}.polygon needs at least 3 points")
    elif "rect" in r:
        v = r["rect"]
        if not (isinstance(v, (list, tuple)) and len(v) == 4):
            raise BuildingSpecError(f"{what}.rect must be [x, y, w, d]")
        poly = rect_poly(num(v[0], what), num(v[1], what), num(v[2], what, 0.1), num(v[3], what, 0.1))
    else:
        raise BuildingSpecError(f"{what} needs 'polygon' or 'rect'")
    if area(poly) < 0.01:
        raise BuildingSpecError(f"{what} has no area")
    rid = str(r.get("id") or slug(r.get("name", ""), f"r{len(ids) + 1}"))
    if rid in ids:
        raise BuildingSpecError(f"duplicate room id '{rid}'")
    ids.add(rid)
    return {"id": rid, "name": str(r.get("name", rid)), "polygon": poly, "is_rect": "rect" in r or _is_rect(poly),
            "floor_color": str(r.get("floor_color") or "#c9b8a0")}


def _is_rect(poly: list[list[float]]) -> bool:
    x0, y0, x1, y1 = bbox(poly)
    return len(poly) == 4 and abs(area(poly) - (x1 - x0) * (y1 - y0)) < 1e-6


def _wall(w: object, what: str, height: float) -> dict[str, Any]:
    if not isinstance(w, dict):
        raise BuildingSpecError(f"{what} must be an object")
    a, b = point(w.get("a"), f"{what}.a"), point(w.get("b"), f"{what}.b")
    if a == b:
        raise BuildingSpecError(f"{what} has zero length")
    return {"id": w.get("id"), "a": a, "b": b, "thickness": num(w.get("thickness", WALL_THICKNESS), what, 0.02),
            "height": num(w.get("height", height), what, 0.2)}


def _roof(r: object) -> dict[str, Any] | None:
    if r is None:
        return None
    if not isinstance(r, dict) or r.get("type", "flat") not in ROOF_TYPES:
        raise BuildingSpecError(f"roof.type must be one of {ROOF_TYPES}")
    return {"type": r.get("type", "flat"), "overhang": num(r.get("overhang", 0.35), "roof.overhang", 0.0),
            "color": r.get("color")}


def _color(v: object, what: str) -> str | None:
    """Optional `#rrggbb` colour; None when absent."""
    if v is None:
        return None
    if not isinstance(v, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
        raise BuildingSpecError(f"{what} must be a #rrggbb colour")
    return v.lower()
