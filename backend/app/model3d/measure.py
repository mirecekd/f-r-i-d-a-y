# backend/app/model3d/measure.py
"""Text rendering and geometry helpers for the model tools (tree view, world position, distance)."""

import json
import math

from app.model3d.model import Model, ModelError, Part


def world_pos(model: Model, part: Part) -> list[float]:
    """Origin of a part in model units. Parent translation and scale count; parent rotation is ignored."""
    chain, cur = [], part
    while cur is not None:
        chain.append(cur)
        cur = model.parts.get(cur.parent) if cur.parent else None
    pos = [0.0, 0.0, 0.0]
    for p in reversed(chain):
        scale = _scale_of(model.parts[p.parent] if p.parent else None)
        pos = [pos[i] + p.pos[i] * scale[i] for i in range(3)]
    return pos


def _scale_of(part: Part | None) -> list[float]:
    if part is None:
        return [1.0, 1.0, 1.0]
    s = part.scale
    return [float(s)] * 3 if isinstance(s, (int, float)) else [float(x) for x in s]


def measure(model: Model, a: str, b: str) -> dict:
    for pid in (a, b):
        if pid not in model.parts:
            raise ModelError(f"unknown part '{pid}'")
    pa, pb = world_pos(model, model.parts[a]), world_pos(model, model.parts[b])
    d = [round(pb[i] - pa[i], 6) for i in range(3)]
    return {"distance": round(math.sqrt(sum(x * x for x in d)), 6), "delta": d, "units": model.units,
            "note": "between part origins; parent rotation ignored"}


def describe_model(model: Model, max_lines: int = 300) -> str:
    """Compact text tree: one line per part with id, kind, layer, pos, size, tags and props."""
    lines = [f"model {model.id} units={model.units} parts={len(model.parts)}"]
    for name, lay in sorted(model.layers.items(), key=lambda kv: kv[1].get("z_index", 0)):
        lines.append(f"layer {name}: {json.dumps(lay, separators=(',', ':'))}")

    def walk(pid: str | None, depth: int) -> None:
        for p in model.children(pid):
            if len(lines) >= max_lines:
                return
            bits = [f"{p.id} {p.kind}", f"L={p.layer}", f"pos={p.pos}"]
            if p.scale != 1.0:
                bits.append(f"scale={p.scale}")
            if p.color:
                bits.append(p.color)
            if not p.visible:
                bits.append("hidden")
            if p.tags:
                bits.append("tags=" + ",".join(p.tags))
            if p.props:
                bits.append("props=" + json.dumps(p.props, separators=(",", ":"))[:200])
            lines.append("  " * depth + "- " + " ".join(bits))
            walk(p.id, depth + 1)

    walk(None, 0)
    if len(lines) >= max_lines:
        lines.append(f"... truncated at {max_lines} lines")
    return "\n".join(lines)
