# backend/app/model3d/packs/pcb/spec.py
"""Validation and normalisation of a PCB spec; every error is a PcbSpecError (a ModelError)."""

import math
import re
from typing import Any

from app.model3d.model import ModelError

KINDS = ("resistor", "capacitor", "led", "soic", "qfp", "pin_header", "usb_c", "crystal", "esp32_module", "generic")
TRACE_LAYERS = ("top", "bottom", "inner1", "inner2")
REF_RE = re.compile(r"^[A-Za-z0-9_]{1,20}$")


class PcbSpecError(ModelError):
    """The PCB spec is invalid."""


def _num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _xy(v: object, size: list[float], what: str) -> list[float]:
    if not (isinstance(v, (list, tuple)) and len(v) == 2 and all(_num(x) for x in v)):
        raise PcbSpecError(f"{what}: position must be [x, y] numbers")
    if not (0 <= v[0] <= size[0] and 0 <= v[1] <= size[1]):
        raise PcbSpecError(f"{what}: position {list(v)} is outside the board {size} mm")
    return [float(v[0]), float(v[1])]


def _items(spec: dict[str, Any], key: str) -> list[dict[str, Any]]:
    items = spec.get(key) or []
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        raise PcbSpecError(f"'{key}' must be a list of objects")
    return items


def validate_trace(t: dict[str, Any], size: list[float], layers: int, what: str = "trace") -> dict[str, Any]:
    layer = t.get("layer", "top")
    if layer not in TRACE_LAYERS or (layers == 2 and layer.startswith("inner")):
        raise PcbSpecError(f"{what}: layer '{layer}' is not available on a {layers}-layer board")
    width = t.get("width_mm", 0.25)
    if not (_num(width) and 0.02 <= width <= 10):
        raise PcbSpecError(f"{what}: width_mm must be 0.02..10")
    pts = t.get("points")
    if not (isinstance(pts, list) and len(pts) >= 2):
        raise PcbSpecError(f"{what}: needs at least two points")
    pts = [_xy(p, size, what) for p in pts]
    if any(a == b for a, b in zip(pts, pts[1:], strict=False)):
        raise PcbSpecError(f"{what}: consecutive points must differ")
    net = t.get("net")
    if not isinstance(net, str) or not net:
        raise PcbSpecError(f"{what}: net must be a non-empty string")
    return {"net": net, "layer": layer, "width_mm": float(width), "points": pts}


def validate(spec: object) -> dict[str, Any]:
    """Return a normalised copy of `spec` or raise PcbSpecError."""
    if not isinstance(spec, dict):
        raise PcbSpecError("spec must be an object")
    size = spec.get("size_mm")
    if not (isinstance(size, list) and len(size) == 2 and all(_num(x) and 1 <= x <= 1000 for x in size)):
        raise PcbSpecError("size_mm must be [width, height] in 1..1000 mm")
    size = [float(size[0]), float(size[1])]
    thick = spec.get("thickness_mm", 1.6)
    if not (_num(thick) and 0.2 <= thick <= 6):
        raise PcbSpecError("thickness_mm must be 0.2..6")
    layers = spec.get("layers", 2)
    if layers not in (2, 4):
        raise PcbSpecError("layers must be 2 or 4")
    comps, refs = [], set()
    for c in _items(spec, "components"):
        ref = c.get("ref")
        if not isinstance(ref, str) or not REF_RE.match(ref) or ref in refs:
            raise PcbSpecError(f"component ref {ref!r} must be a unique [A-Za-z0-9_] name up to 20 characters")
        refs.add(ref)
        if c.get("kind") not in KINDS:
            raise PcbSpecError(f"component {ref}: kind {c.get('kind')!r} unknown; known: {list(KINDS)}")
        side = c.get("side", "top")
        if side not in ("top", "bottom"):
            raise PcbSpecError(f"component {ref}: side must be top or bottom")
        rot = c.get("rot", 0)
        pins = c.get("pins")
        if not _num(rot) or (pins is not None and not (isinstance(pins, int) and not isinstance(pins, bool) and 1 <= pins <= 200)):
            raise PcbSpecError(f"component {ref}: rot must be a number and pins an integer 1..200")
        nets = c.get("nets") or {}
        if not isinstance(nets, dict):
            raise PcbSpecError(f"component {ref}: nets must map pin -> net")
        comps.append({**c, "side": side, "rot": float(rot), "pos": _xy(c.get("pos"), size, f"component {ref}"), "nets": nets})
    outline = spec.get("outline")
    if outline is not None:
        if not (isinstance(outline, list) and len(outline) >= 3):
            raise PcbSpecError("outline must be a polygon of at least three points")
        outline = [_xy(p, size, "outline") for p in outline]
    vias = [{"pos": _xy(v.get("pos"), size, "via"), "drill_mm": float(v.get("drill_mm", 0.3)), "net": str(v.get("net", ""))}
            for v in _items(spec, "vias")]
    if any(not 0.1 <= v["drill_mm"] <= 3 for v in vias):
        raise PcbSpecError("via drill_mm must be 0.1..3")
    silk = [{"text": str(s.get("text", "")), "pos": _xy(s.get("pos"), size, "silk"), "size": float(s.get("size", 1.5))}
            for s in _items(spec, "silk")]
    return {"name": str(spec.get("name") or "pcb"), "size": size, "thickness": float(thick), "layers": layers,
            "components": comps, "traces": [validate_trace(t, size, layers) for t in _items(spec, "traces")],
            "vias": vias, "silk": silk, "outline": outline, "silk_refs": bool(spec.get("silk_refs", False))}
