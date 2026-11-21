# backend/app/model3d/bounds.py
"""Conservative bounding boxes of a model, the auto-fit scene scale and the camera op that frames a model."""

import math
from typing import Any

from app.model3d.model import Model, Part
from app.model3d.visible import visible_parts

FIT_LONGEST = 4.0  # scene units the longest side is scaled to when auto-fit applies
FIT_MIN, FIT_MAX = 1.0, 20.0  # auto-fit only acts when the longest side would fall outside this range
CAMERA_DIR = (0.65, 0.5, 0.9)  # 3/4 view from front-right-above
Bounds = tuple[list[float], list[float]]


def _vec_scale(s: Any) -> list[float]:
    return [float(x) for x in s] if isinstance(s, list) else [float(s)] * 3


def _rotate(v: list[float], rot: list[float]) -> list[float]:
    """Euler XYZ as in three.js: the vector is rotated about z, then y, then x."""
    x, y, z = v
    c, s = math.cos(rot[2]), math.sin(rot[2])
    x, y = c * x - s * y, s * x + c * y
    c, s = math.cos(rot[1]), math.sin(rot[1])
    x, z = c * x + s * z, -s * x + c * z
    c, s = math.cos(rot[0]), math.sin(rot[0])
    y, z = c * y - s * z, s * y + c * z
    return [x, y, z]


def _local_box(p: Part) -> Bounds:
    """Local axis-aligned box of a part before its own scale; boxes, cylinders etc. are unit sized."""
    g = p.geom
    if p.kind == "polyline" and g.get("pts"):
        pts = [list(q) + [0.0] * (3 - len(q)) for q in g["pts"] if isinstance(q, (list, tuple))]
        if pts:
            return [min(q[i] for q in pts) for i in range(3)], [max(q[i] for q in pts) for i in range(3)]
    if p.kind == "extrude" and g.get("outline"):
        pts = [q for q in g["outline"] if isinstance(q, (list, tuple)) and len(q) >= 2]
        h = g.get("height", 1.0) if isinstance(g.get("height", 1.0), (int, float)) else 1.0
        if pts:
            return [min(q[0] for q in pts), min(q[1] for q in pts), -abs(h)], [max(q[0] for q in pts), max(q[1] for q in pts), abs(h)]
    if p.kind == "lathe" and g.get("profile"):
        pts = [q for q in g["profile"] if isinstance(q, (list, tuple)) and len(q) >= 2]
        if pts:
            r = max(abs(q[0]) for q in pts)
            return [-r, min(q[1] for q in pts), -r], [r, max(q[1] for q in pts), r]
    if p.kind in ("group", "label", "text", "image", "gltf", "csg"):
        return [0.0] * 3, [0.0] * 3
    return [-0.5] * 3, [0.5] * 3


def _world_corners(model: Model, p: Part, pos: dict[str, list[float]]) -> list[list[float]]:
    lo, hi = _local_box(p)
    corners = [[(lo, hi)[(i >> a) & 1][a] for a in range(3)] for i in range(8)]
    chain: list[Part] = []
    cur: Part | None = p
    while cur is not None:
        chain.append(cur)
        cur = model.parts.get(cur.parent) if cur.parent else None
    out = []
    for c in corners:
        v = c
        for q in chain:
            sc = _vec_scale(q.scale)
            v = [a + b for a, b in zip(_rotate([v[i] * sc[i] for i in range(3)], q.rot), pos.get(q.id, q.pos), strict=True)]
        out.append(v)
    return out


def model_bounds(model: Model, pos: dict[str, list[float]] | None = None) -> Bounds | None:
    """Axis-aligned box of the visible parts in model units; `pos` overrides local part positions. None when empty."""
    pts: list[list[float]] = []
    for p in visible_parts(model):
        pts += _world_corners(model, p, pos or {})
    if not pts:
        return None
    return [min(q[i] for q in pts) for i in range(3)], [max(q[i] for q in pts) for i in range(3)]


def longest_side(b: Bounds) -> float:
    return max(b[1][i] - b[0][i] for i in range(3))


def effective_scale(model: Model) -> float:
    """Scene scale of the model root: `scale_to_scene`, or an auto-fit scale when the model would be tiny or huge."""
    b = model_bounds(model)
    if not model.auto_fit or b is None:
        return model.scale_to_scene
    side = longest_side(b) * model.scale_to_scene
    if side <= 0 or FIT_MIN <= side <= FIT_MAX:
        return model.scale_to_scene
    return FIT_LONGEST / longest_side(b)


def frame_op(model: Model, b: Bounds) -> dict[str, Any]:
    """One `camera` op that frames the box `b` (model units) from a 3/4 angle."""
    k = effective_scale(model)
    centre = [(b[0][i] + b[1][i]) / 2 * k for i in range(3)]
    radius = max(math.sqrt(sum(((b[1][i] - b[0][i]) * k) ** 2 for i in range(3))) / 2, 0.25)
    n = math.sqrt(sum(x * x for x in CAMERA_DIR))
    dist = radius * 2.6
    return {"op": "camera", "pos": [round(centre[i] + CAMERA_DIR[i] / n * dist, 4) for i in range(3)],
            "look": [round(x, 4) for x in centre]}


def changed_substantially(before: Bounds | None, after: Bounds | None) -> bool:
    """True for a new model (no bounds before) or when the longest side grew or shrank by half."""
    if after is None:
        return False
    if before is None:
        return True
    a, b = longest_side(before), longest_side(after)
    return a <= 0 or not (0.67 <= b / a <= 1.5)
