# backend/app/model3d/packs/enclosure/__init__.py
"""Enclosure pack: case, lid, screw posts, cut-outs and vents as parts for the generic model API."""

from typing import Any

from app.model3d.model import ModelError
from app.model3d.packs import register_pack
from app.model3d.packs.enclosure.build import build_parts
from app.model3d.packs.enclosure.spec import normalise


def enclosure_from_spec(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Part dicts for `spec` (see docs/protocol.md). Layers: case, posts, lid, cutters. Needs `model_id` when use_csg is set."""
    s = normalise(spec)
    if s["use_csg"] and not isinstance(s["model_id"], str):
        raise ModelError("use_csg needs model_id (the id of the model the parts are added to)")
    return build_parts(s)


def _defaults(spec: dict[str, Any]) -> dict[str, Any]:
    """A 60x40x20 mm snap-lid case unless the spec already sizes it (inner_mm or fit_to_part)."""
    return {} if "inner_mm" in spec or "fit_to_part" in spec else {"inner_mm": [60, 40, 20]}


_EXAMPLE = {"fit_to_part": {"model": "pcb", "layer": "board", "margin_mm": 2}, "wall_mm": 2, "lid": {"type": "snap"}}
register_pack("enclosure", enclosure_from_spec, example=_EXAMPLE, defaults=_defaults)
