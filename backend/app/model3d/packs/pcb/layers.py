# backend/app/model3d/packs/pcb/layers.py
"""PCB layer stack, colours and the Part dict helper. Model units are mm; plan (x, y) maps to model (x, -y) about the board centre."""

import math
from typing import Any

Z_INDEX = {"components_bottom": -1, "copper_bottom": 0, "inner2": 1, "inner1": 2, "vias": 3, "board": 4,
           "copper_top": 5, "mask_top": 6, "silk_top": 7, "components": 8}
TRACE_LAYER = {"top": "copper_top", "bottom": "copper_bottom", "inner1": "inner1", "inner2": "inner2"}
COPPER_H = 0.05  # drawn copper thickness, exaggerated a little to stay visible
MASK_H = 0.06
PAD_H = 0.08
COLOR = {"board": "#b59a5c", "copper": "#c87533", "pad": "#e0c070", "mask": "#0f9a50", "silk": "#f2f2f2",
         "via": "#f0cf6a", "plane": "#b8733a"}
OPACITY = {"board": 0.85, "mask": 0.4, "copper": 0.95, "component": 0.95, "plane": 0.3}


class Frame:
    """Board geometry shared by all builders."""

    def __init__(self, size: list[float], thickness: float, layers: int):
        self.w, self.h, self.t, self.layers = size[0], size[1], thickness, layers

    def xz(self, x: float, y: float) -> tuple[float, float]:
        """Plan (x, y) in mm from the board's lower-left corner -> model (x, z)."""
        return round(x - self.w / 2, 4), round(-(y - self.h / 2), 4)

    def layer_y(self, layer: str) -> float:
        """Model y of the centre plane of a copper layer."""
        return {"copper_top": self.t / 2 + COPPER_H / 2, "copper_bottom": -self.t / 2 - COPPER_H / 2,
                "inner1": self.t / 6, "inner2": -self.t / 6}[layer]

    @property
    def top(self) -> float:
        return self.t / 2

    def to_dict(self) -> dict[str, Any]:
        return {"w": self.w, "h": self.h, "t": self.t, "layers": self.layers}


def part(pid: str, kind: str, layer: str, pos: list[float], scale: Any = 1.0, *, rot: list[float] | None = None,
         color: str | None = None, opacity: float | None = None, parent: str | None = None, name: str = "",
         props: dict[str, Any] | None = None, geom: dict[str, Any] | None = None, tags: list[str] | None = None) -> dict[str, Any]:
    d: dict[str, Any] = {"id": pid, "kind": kind, "name": name or pid, "pos": [round(float(v), 4) for v in pos],
                         "rot": [round(float(v), 5) for v in (rot or [0, 0, 0])], "scale": scale, "layer": layer}
    if isinstance(scale, list):
        d["scale"] = [round(float(v), 4) for v in scale]
    for k, v in (("color", color), ("opacity", opacity), ("parent", parent)):
        if v is not None:
            d[k] = v
    if props:
        d["props"] = props
    if geom:
        d["geom"] = geom
    if tags:
        d["tags"] = tags
    return d


def box(pid: str, layer: str, cx: float, cy: float, z0: float, sx: float, sy: float, h: float, **kw: Any) -> dict[str, Any]:
    """Axis-aligned box in model space from plan footprint centre (cx, cy), size (sx, sy), base z0 and height h."""
    return part(pid, "box", layer, [cx, z0 + h / 2, -cy], [sx, h, sy], **kw)


def cyl(pid: str, layer: str, cx: float, cy: float, z0: float, d: float, h: float, **kw: Any) -> dict[str, Any]:
    return part(pid, "cylinder", layer, [cx, z0 + h / 2, -cy], [d, h, d], **kw)


def rot2(x: float, y: float, deg: float) -> tuple[float, float]:
    a = math.radians(deg)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
