# backend/app/model3d/packs/pcb/__init__.py
"""PCB domain pack: `pcb_from_spec(spec)` builds a layered board with procedural component bodies."""

from typing import Any

from app.model3d.packs import register_pack
from app.model3d.packs.pcb.assemble import component_parts
from app.model3d.packs.pcb.board import board_parts, silk_parts, via_parts
from app.model3d.packs.pcb.layers import Z_INDEX, Frame
from app.model3d.packs.pcb.spec import PcbSpecError, validate
from app.model3d.packs.pcb.traces import pcb_trace_diff_helper, trace_ids, trace_parts

__all__ = ["PcbSpecError", "pcb_from_spec", "pcb_layer_settings", "pcb_trace_diff_helper"]


def pcb_layer_settings() -> dict[str, dict[str, Any]]:
    """Layer stack for the model (`Model.layers`): z_index orders `model_explode by=layer` bottom to top."""
    return {name: {"z_index": z} for name, z in Z_INDEX.items()}


def pcb_from_spec(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Part dicts: board, mask_top, inner planes, trace groups, pads, vias, silkscreen and component groups."""
    s = validate(spec)
    f = Frame(s["size"], s["thickness"], s["layers"])
    parts = board_parts(f, s)
    parts[0]["props"]["layer_z_index"] = dict(Z_INDEX)
    for tid, t in zip(trace_ids(s), s["traces"], strict=True):
        parts += trace_parts(f, tid, t)
    parts += via_parts(f, s)
    for c in s["components"]:
        parts += component_parts(f, c)
    parts += silk_parts(f, s, s["components"])
    ids = [p["id"] for p in parts]
    if len(ids) != len(set(ids)):
        raise PcbSpecError("generated part ids collide; check for duplicate refs or pins")
    return parts


def _defaults(spec: dict[str, Any]) -> dict[str, Any]:
    """A 60x40 mm two-layer board (or the given size_mm) with a resistor, a capacitor and an LED across its middle."""
    size = spec.get("size_mm")
    w, h = 60.0, 40.0
    if isinstance(size, (list, tuple)) and len(size) == 2 and all(isinstance(v, (int, float)) and v > 0 for v in size):
        w, h = float(size[0]), float(size[1])
    return {"name": "pcb", "size_mm": [w, h], "layers": 2, "components": [
        {"ref": "R1", "kind": "resistor", "value": "10k", "footprint": "0603", "pos": [w * 0.25, h / 2]},
        {"ref": "C1", "kind": "capacitor", "footprint": "0805", "pos": [w * 0.5, h / 2]},
        {"ref": "D1", "kind": "led", "value": "green", "pos": [w * 0.75, h / 2]}]}


_EXAMPLE = {"size_mm": [60, 40], "layers": 2, "components": [{"ref": "R1", "kind": "resistor", "pos": [15, 20]}],
            "traces": [{"net": "SIG", "layer": "top", "points": [[15, 20], [30, 20]]}]}
register_pack("pcb", pcb_from_spec, example=_EXAMPLE, defaults=_defaults, layers=lambda parts: pcb_layer_settings())
