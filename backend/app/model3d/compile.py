# backend/app/model3d/compile.py
"""Compile a Model into scene DSL ops; only the model's own root group is replaced."""

from typing import Any

from app.model3d.bounds import effective_scale
from app.model3d.model import Model, Part
from app.model3d.visible import visible_parts
from app.scene_schema import check_op


def root_id(model: Model) -> str:
    return f"model:{model.id}"


def part_scene_id(model: Model, part_id: str) -> str:
    return f"m:{model.id}:{part_id}"


def part_obj(model: Model, part: Part, obj_id: str, parent_id: str, style: dict[str, Any] | None = None) -> dict[str, Any]:
    """One scene object for a part: layer colour overrides the part colour, opacities multiply. `style` overrides last."""
    lay = model.layer(part.layer)
    obj: dict[str, Any] = {"id": obj_id, "kind": part.kind, "parent": parent_id,
                           "pos": list(part.pos), "rot": list(part.rot), "scale": part.scale, **part.geom}
    color = lay["color"] or part.color
    if color:
        obj["color"] = color
    opacity = (1.0 if part.opacity is None else part.opacity) * lay["opacity"]
    if opacity < 1:
        obj["opacity"] = round(opacity, 4)
    obj.update(style or {})
    return obj


def compile_model(model: Model) -> list[dict[str, Any]]:
    """Ops that replace the model in the scene: del the root group (cascades), add root, add parts parent-first."""
    root = root_id(model)
    ops: list[dict[str, Any]] = [
        {"op": "del", "id": root},
        {"op": "add", "obj": {"id": root, "kind": "group", "scale": effective_scale(model)}},
    ]
    for p in visible_parts(model):
        parent = part_scene_id(model, p.parent) if p.parent else root
        ops.append({"op": "add", "obj": part_obj(model, p, part_scene_id(model, p.id), parent)})
    for op in ops:
        check_op(op)
    return ops
