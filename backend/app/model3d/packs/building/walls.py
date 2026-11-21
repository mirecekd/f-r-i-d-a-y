# backend/app/model3d/packs/building/walls.py
"""Wall segments of a storey and the box pieces of one wall (openings are real gaps, no CSG)."""

import math
from typing import Any

from app.model3d.packs.building.geom import unique_segments
from app.model3d.packs.building.parts import box, group

WALL_COLOR = "#e8e2d6"


def wall_list(storey: dict[str, Any]) -> list[dict[str, Any]]:
    """Explicit walls when the storey lists any, else one wall per unique room edge (shared edges merged)."""
    if storey["walls"]:
        raw = [(w["a"], w["b"], w["thickness"], w["height"], w["id"]) for w in storey["walls"]]
    else:
        raw = [(a, b, 0.2, storey["height"], None) for a, b in unique_segments([r["polygon"] for r in storey["rooms"]])]
    out: list[dict[str, Any]] = []
    for i, (a, b, t, h, wid) in enumerate(raw, 1):
        out.append({"id": str(wid or f"w{i}"), "a": a, "b": b, "thickness": t, "height": h, "length": math.dist(a, b)})
    return out


def yaw(a: list[float], b: list[float]) -> float:
    """Rotation about y that turns local +x onto the plan direction a->b (plan y is world z)."""
    return -math.atan2(b[1] - a[1], b[0] - a[0])


def rects(length: float, height: float, holes: list[dict[str, Any]]) -> list[tuple[float, float, float, float]]:
    """Solid rectangles (x0, x1, y0, y1) of a wall of `length` x `height` around the sorted opening holes."""
    out: list[tuple[float, float, float, float]] = []
    cur = 0.0
    for o in holes:
        if o["offset"] > cur + 1e-6:
            out.append((cur, o["offset"], 0.0, height))
        if o["sill"] > 1e-6:
            out.append((o["offset"], o["offset"] + o["width"], 0.0, o["sill"]))
        top = o["sill"] + o["height"]
        if top < height - 1e-6:
            out.append((o["offset"], o["offset"] + o["width"], top, height))
        cur = o["offset"] + o["width"]
    if length > cur + 1e-6:
        out.append((cur, length, 0.0, height))
    return out


def wall_parts(w: dict[str, Any], holes: list[dict[str, Any]], pid: str, parent: str, layer: str,
               props: dict[str, Any], color: str = WALL_COLOR) -> list[dict[str, Any]]:
    """A wall group at the segment midpoint with one box child per solid rectangle."""
    a, b, t, length = w["a"], w["b"], w["thickness"], w["length"]
    mid = [(a[0] + b[0]) / 2, w.get("base", 0.0), (a[1] + b[1]) / 2]
    parts = [group(pid, f"wall {w['id']}", mid, layer, parent, [0.0, yaw(a, b), 0.0], {**props, "length": round(length, 4)})]
    for i, (x0, x1, y0, y1) in enumerate(rects(length, w["height"], holes)):
        x0 -= t / 2 if x0 <= 1e-6 else 0.0  # run past the segment ends so corners close
        x1 += t / 2 if x1 >= length - 1e-6 else 0.0
        parts.append(box(f"{pid}-p{i}", "wall piece", [(x0 + x1) / 2 - length / 2, (y0 + y1) / 2, 0.0],
                         [x1 - x0, y1 - y0, t], layer, color, pid, props=props))
    return parts
