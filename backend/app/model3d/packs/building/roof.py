# backend/app/model3d/packs/building/roof.py
"""Flat slab or gable roof over a footprint (boxes plus two extruded gable ends)."""

import math
from typing import Any

from app.model3d.packs.building.parts import box, group

ROOF_COLOR = "#c8553d"
GABLE_COLOR = "#e9d8b4"
THICK = 0.12
PITCH = 0.55  # rise per half-span


def roof_parts(kind: str, bounds: tuple[float, float, float, float], top: float, overhang: float,
               color: str | None, layer: str, props: dict[str, Any]) -> list[dict[str, Any]]:
    """Roof parts for plan `bounds` (x0, y0, x1, y1) sitting on height `top`; all under group 'roof'."""
    x0, y0, x1, y1 = bounds
    x_len, z_len = x1 - x0, y1 - y0
    centre = [(x0 + x1) / 2, top, (y0 + y1) / 2]
    color = color or ROOF_COLOR
    if kind == "flat":
        return [group("roof", "roof", centre, layer, None, props=props),
                box("roof-slab", "slab", [0, THICK / 2, 0], [x_len + 2 * overhang, THICK, z_len + 2 * overhang], layer, color, "roof", props=props)]
    ridge_x = x_len >= z_len  # the ridge runs along the longer side
    span, length = (z_len, x_len) if ridge_x else (x_len, z_len)
    half = span / 2
    rise = half * PITCH
    theta = math.atan2(rise, half)
    hw = half + overhang
    slope = hw / math.cos(theta)
    out = [group("roof", "roof", centre, layer, None, [0.0, math.pi / 2 if ridge_x else 0.0, 0.0], props)]
    for sign, name in ((1, "e"), (-1, "w")):
        out.append(box(f"roof-slope-{name}", f"slope {name}", [sign * (hw / 2), (rise - overhang * math.tan(theta)) / 2 + THICK / 2, 0],
                       [slope, THICK, length + 2 * overhang], layer, color, "roof", rot=[0.0, 0.0, -sign * theta], props=props))
    for name, z in (("s", -length / 2), ("n", length / 2 - THICK)):
        out.append({"id": f"roof-gable-{name}", "kind": "extrude", "name": f"gable {name}", "parent": "roof", "pos": [0, 0, z],
                    "rot": [math.pi / 2, 0.0, 0.0], "color": GABLE_COLOR, "layer": layer, "props": props,
                    "geom": {"outline": [[-half, 0.0], [half, 0.0], [0.0, -rise]], "height": THICK, "floor": False}})
    return out
