# backend/app/workshop/draw.py
"""Compose everything the scene needs to show one workshop record: stage, model, params, notes and the camera pose."""

import json
from dataclasses import dataclass, field
from typing import Any

from app.model3d.bounds import Bounds
from app.workshop import stage, store
from app.workshop.spec import expand

MAX_SPEC_BYTES = 64_000


@dataclass
class Drawn:
    ops: list[dict[str, Any]]
    camera: dict[str, Any]  # a `camera` op in scene coordinates
    bounds: Bounds | None
    params: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    parts: int = 0


def check_spec_size(spec: object) -> dict[str, Any]:
    """The spec as a dict, or WorkshopError: not an object, not JSON-safe (NaN, cycles, odd types) or over 64 kB."""
    if not isinstance(spec, dict):
        raise store.WorkshopError("spec must be a JSON object (the part tree)")
    try:
        size = len(json.dumps(spec, allow_nan=False, ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError, RecursionError) as e:
        raise store.WorkshopError(
            f"spec is not plain JSON data (non-finite number or unsupported value): {e}"[:240]
        ) from e
    if size > MAX_SPEC_BYTES:
        raise store.WorkshopError(
            f"spec is too big ({size // 1000} kB, the limit is {MAX_SPEC_BYTES // 1000} kB); use arrays and mirror"
        )
    return spec


def draw(rec: dict[str, Any]) -> Drawn:
    """Ops that replace the stage and the model of `rec`. Raises SpecError or ModelError when the stored spec is invalid."""
    wid, origin = rec["id"], store.origin_of(rec["origin_n"])
    spec = rec["spec"]
    if spec is None:
        radius = stage.MIN_RADIUS
        ops = stage.stage_ops(wid, rec["title"], origin, radius, 1.0) + stage.clear_model_ops(wid)
        return Drawn(ops, stage.camera_op(None, None, origin, radius), None)
    expanded = expand(spec)
    model = stage.build_model(wid, expanded.parts, spec.get("units", "mm"), origin)
    bounds, scale = stage.model_extent(model)
    radius = stage.table_radius(bounds, scale)
    ops = stage.stage_ops(wid, rec["title"], origin, radius, stage.top_of(bounds, scale)) + stage.model_ops(model)
    return Drawn(
        ops,
        stage.camera_op(model, bounds, origin, radius),
        bounds,
        expanded.params,
        expanded.notes,
        len(expanded.parts),
    )
