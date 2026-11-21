# backend/app/model3d/explode.py
"""Generic exploded view: `set` ops that move parts apart (or back) without touching the model."""

import math
from typing import Any

from app.model3d.bounds import longest_side, model_bounds
from app.model3d.compile import part_scene_id, visible_parts
from app.model3d.model import Model, ModelError, Part

AXES = {"x": 0, "y": 1, "z": 2}
MODES = ("layer", "group", "radial")
ANIM_MS = 600


def _unit_of(model: Model, p: Part, mode: str) -> bool:
    """True when `p` is moved by its own offset (children then follow through the scene parent link)."""
    if p.parent is None:
        return True
    return mode == "layer" and model.parts[p.parent].layer != p.layer


def _extent(model: Model, ax: int) -> float:
    vals = [p.pos[ax] for p in model.parts.values()]
    return max(max(vals) - min(vals), 1.0) if vals else 1.0


def explode(model: Model, factor: float, by: str = "layer", axis: str = "y", spacing: float | None = None) -> list[dict[str, Any]]:
    """Return `set` ops. factor 0 restores the original positions (animated). Offsets are in model units.

    layer: layers ordered by z_index are stacked along `axis`; group: each top-level part is stacked
    along `axis` in model order; radial: top-level parts move away from the centroid of top-level parts.
    """
    if by not in MODES or axis not in AXES:
        raise ModelError(f"by must be one of {MODES} and axis x|y|z")
    if isinstance(factor, bool) or not isinstance(factor, (int, float)) or not math.isfinite(factor):
        raise ModelError("factor must be a number")
    ax = AXES[axis]
    b = model_bounds(model)
    step = spacing if spacing is not None else max(_extent(model, ax) * 0.5, longest_side(b) * 0.1 if b else 0.0)
    parts = [p for p in visible_parts(model) if _unit_of(model, p, by)]
    offsets: dict[str, list[float]] = {}
    if by == "layer":
        order = sorted({p.layer for p in model.parts.values()}, key=lambda n: (model.layer(n)["z_index"], n))
        for p in parts:
            offsets[p.id] = _along(ax, order.index(p.layer) * step)
    elif by == "group":
        tops = [p.id for p in model.children(None)]
        for p in parts:
            offsets[p.id] = _along(ax, tops.index(p.id) * step)
    else:
        tops = model.children(None)
        c = [sum(t.pos[i] for t in tops) / len(tops) for i in range(3)] if tops else [0, 0, 0]
        for p in parts:
            d = [p.pos[i] - c[i] for i in range(3)]
            n = math.sqrt(sum(x * x for x in d))
            d = [x / n for x in d] if n > 1e-9 else _along(ax, 1.0)
            offsets[p.id] = [x * step for x in d]
    return [{"op": "set", "id": part_scene_id(model, p.id),
             "props": {"pos": [round(p.pos[i] + offsets[p.id][i] * factor, 6) for i in range(3)]}, "ms": ANIM_MS}
            for p in parts]


def _along(ax: int, v: float) -> list[float]:
    out = [0.0, 0.0, 0.0]
    out[ax] = v
    return out
