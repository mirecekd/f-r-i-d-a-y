# backend/app/model3d/packs/building/plan.py
"""Convert the vision analysis of a floor plan into a building spec by deterministic row packing."""

import re
from typing import Any

from app.model3d.packs.building.spec import STOREY_HEIGHT, BuildingSpecError, slug

DEFAULT_ROOM = (3.5, 4.0)
MAX_ROW_WIDTH = 12.0
_DIMS = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:m|cm|mm)?\s*[x×*]\s*(\d+(?:[.,]\d+)?)\s*(m|cm|mm)?", re.IGNORECASE)
_UNIT = {"m": 1.0, "cm": 0.01, "mm": 0.001}


def parse_dimensions(text: object) -> tuple[float, float] | None:
    """(width, depth) in metres from text like '4.6 x 5.2 m', '460x520 cm' or '4,6 × 5,2'; None when absent.

    A bare pair without unit is metres when both values are below 100, else centimetres.
    """
    m = _DIMS.search(text) if isinstance(text, str) else None
    if not m:
        return None
    a, b = (float(g.replace(",", ".")) for g in m.group(1, 2))
    unit = _UNIT.get((m.group(3) or "").lower()) or (1.0 if max(a, b) < 100 else 0.01)
    if a * unit <= 0 or b * unit <= 0:
        return None
    return round(a * unit, 3), round(b * unit, 3)


def plan_to_spec(vision_json: dict[str, Any]) -> dict[str, Any]:
    """Building spec from the vision analysis `{kind: 'floorplan', rooms: [{name, dimensions}], ...}`.

    Heuristic and deliberately simple: every room becomes a rectangle (its stated width x depth in metres,
    or 3.5 x 4.0 m when the size is missing or unreadable) and the rooms are packed left to right in the
    order given into rows that wrap at 12 m. Walls between neighbours are shared only where edges happen to
    line up; real adjacency, door and window positions, non-rectangular rooms and multiple storeys are NOT
    recovered from the image - the spec is a starting point the user corrects with building_scale_to_room or edits.
    The first dimension is taken as x (width), the second as y (depth). Raises BuildingSpecError without rooms.
    """
    if not isinstance(vision_json, dict):
        raise BuildingSpecError("vision analysis must be an object")
    raw = vision_json.get("rooms")
    if not isinstance(raw, list) or not raw:
        raise BuildingSpecError("the analysis lists no rooms to build from")
    rooms: list[dict[str, Any]] = []
    x = y = row_depth = 0.0
    ids: set[str] = set()
    for i, item in enumerate(raw):
        name = item if isinstance(item, str) else str(item.get("name", "")) if isinstance(item, dict) else ""
        dims = parse_dimensions(item.get("dimensions") if isinstance(item, dict) else None)
        w, d = dims or DEFAULT_ROOM
        if x > 0 and x + w > MAX_ROW_WIDTH:
            x, y, row_depth = 0.0, y + row_depth, 0.0
        rid = base = slug(name, f"room{i + 1}")
        n = 2
        while rid in ids:
            rid, n = f"{base}-{n}", n + 1
        ids.add(rid)
        rooms.append({"id": rid, "name": name or f"Room {i + 1}", "rect": [round(x, 3), round(y, 3), w, d]})
        x += w
        row_depth = max(row_depth, d)
    return {"name": "floor plan", "units": "m", "storeys": [{"name": "Ground", "elevation": 0, "height": STOREY_HEIGHT, "rooms": rooms}]}
