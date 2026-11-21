# backend/app/workshop/stage.py
"""The work table of one workshop as ordinary scene objects `ws:<id>:*`, the compiled model and the camera poses."""

import math
from typing import Any

from app.model3d.bounds import Bounds, effective_scale, frame_op, model_bounds
from app.model3d.compile import compile_model, root_id
from app.model3d.model import Model
from app.scene_schema import check_op

Vec = tuple[float, float, float]
ACCENT = "#4fe0d0"
PLATFORM_COLOR = "#0b1118"
MIN_RADIUS, MAX_RADIUS = 3.0, 60.0
RING_POINTS = 72
EMPTY_CAMERA_BACK, EMPTY_CAMERA_UP = 8.0, 3.5


def stage_id(workshop_id: str) -> str:
    return f"ws:{workshop_id}:stage"


def model_id(workshop_id: str) -> str:
    return f"ws{workshop_id}"


def build_model(workshop_id: str, parts: list[dict[str, Any]], units: str, origin: Vec) -> Model:
    """The model3d Model of the expanded parts, placed at the workshop origin (raises ModelError on a bad part)."""
    model = Model.from_dict({"id": model_id(workshop_id), "units": units, "parts": parts, "origin": list(origin)})
    model.validate()
    return model


def model_extent(model: Model) -> tuple[Bounds | None, float]:
    """(bounds in model units, scene scale of the model root)."""
    return model_bounds(model), effective_scale(model)


def table_radius(bounds: Bounds | None, scale: float) -> float:
    """Table radius in scene units: wide enough for the model footprint, at least 3, rounded up to half units."""
    if bounds is None:
        return MIN_RADIUS
    reach = max(math.hypot(x, z) for x in (bounds[0][0], bounds[1][0]) for z in (bounds[0][2], bounds[1][2]))
    wanted = math.ceil((reach * scale * 1.15 + 0.5) * 2) / 2
    return min(MAX_RADIUS, max(MIN_RADIUS, wanted))


def top_of(bounds: Bounds | None, scale: float) -> float:
    return max(1.0, bounds[1][1] * scale) if bounds else 1.0


def stage_ops(workshop_id: str, title: str, origin: Vec, radius: float, top: float) -> list[dict[str, Any]]:
    """Replace the whole table: group at the origin with a dark platform, a thin accent ring and the title text."""
    sid = stage_id(workshop_id)
    ring = [
        [
            round(radius * math.cos(2 * math.pi * i / RING_POINTS), 3),
            0.02,
            round(radius * math.sin(2 * math.pi * i / RING_POINTS), 3),
        ]
        for i in range(RING_POINTS)
    ]
    objs: list[dict[str, Any]] = [
        {"id": sid, "kind": "group", "pos": list(origin)},
        {
            "id": f"ws:{workshop_id}:platform",
            "kind": "cylinder",
            "parent": sid,
            "pos": [0, -0.06, 0],
            "scale": [2 * radius, 0.12, 2 * radius],
            "color": PLATFORM_COLOR,
            "opacity": 0.9,
        },
        {
            "id": f"ws:{workshop_id}:ring",
            "kind": "polyline",
            "parent": sid,
            "pts": ring,
            "closed": True,
            "color": ACCENT,
        },
        {
            "id": f"ws:{workshop_id}:title",
            "kind": "text",
            "parent": sid,
            "text": title[:120],
            "size": 0.45,
            "pos": [0, round(top + 0.9, 3), round(-radius * 0.9, 3)],
            "color": ACCENT,
        },
    ]
    ops: list[dict[str, Any]] = [{"op": "del", "id": sid}, *({"op": "add", "obj": o} for o in objs)]
    for op in ops:
        check_op(op)
    return ops


def model_ops(model: Model) -> list[dict[str, Any]]:
    return compile_model(model)


def clear_model_ops(workshop_id: str) -> list[dict[str, Any]]:
    return [{"op": "del", "id": f"model:{model_id(workshop_id)}"}]


def _shift(v: list[float], origin: Vec) -> list[float]:
    return [round(v[i] + origin[i], 4) for i in range(3)]


def camera_op(model: Model | None, bounds: Bounds | None, origin: Vec, radius: float) -> dict[str, Any]:
    """Camera op (scene coordinates) that looks at the model on the table, or at the empty table."""
    if model is not None and bounds is not None:
        op = frame_op(model, bounds)
        pos, look = op["pos"], op["look"]
        away = [pos[i] - look[i] for i in range(3)]
        scale = max(1.0, radius * 1.6 / max(math.sqrt(sum(a * a for a in away)), 1e-6))  # keep the whole table in view
        pos = [look[i] + away[i] * scale for i in range(3)]
        return {"op": "camera", "pos": _shift(pos, origin), "look": _shift(look, origin)}
    return {
        "op": "camera",
        "pos": _shift([0, EMPTY_CAMERA_UP, EMPTY_CAMERA_BACK], origin),
        "look": _shift([0, 0.8, 0], origin),
    }


def pose_of(op: dict[str, Any]) -> dict[str, list[float]]:
    return {"pos": list(op["pos"]), "look": list(op["look"])}


def root_of(workshop_id: str) -> str:
    return root_id(Model(model_id(workshop_id)))
