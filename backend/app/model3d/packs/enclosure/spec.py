# backend/app/model3d/packs/enclosure/spec.py
"""Enclosure spec normalisation and validation (all sizes in mm, y is up, x/z span the floor)."""

from typing import Any

from app.model3d.model import ModelError

SIDES = ("front", "back", "left", "right", "top", "bottom")
LID_TYPES = ("snap", "screw", "sliding")
MAX_ITEMS = 64


def _pos(v: Any, what: str, n: int = 2, *, positive: bool = False) -> list[float]:
    ok = isinstance(v, (list, tuple)) and len(v) == n and all(isinstance(x, (int, float)) and not isinstance(x, bool) and x == x for x in v)
    if not ok or (positive and any(x <= 0 for x in v)):
        raise ModelError(f"{what} must be {n} {'positive ' if positive else ''}numbers")
    return [float(x) for x in v]


def _num(spec: dict[str, Any], key: str, default: float, *, minimum: float = 0.0) -> float:
    v = spec.get(key, default)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v < minimum or v != v:
        raise ModelError(f"{key} must be a number >= {minimum}")
    return float(v)


def face_extent(side: str, inner: list[float]) -> tuple[float, float]:
    """Usable (u, v) extent of the inner face a cutout on `side` lives in."""
    w, d, h = inner
    return {"front": (w, h), "back": (w, h), "left": (d, h), "right": (d, h), "top": (w, d), "bottom": (w, d)}[side]


def check_cutout(c: Any, inner: list[float], i: int) -> dict[str, Any]:
    if not isinstance(c, dict) or c.get("side") not in SIDES or c.get("shape", "rect") not in ("rect", "round"):
        raise ModelError(f"cutouts[{i}]: needs side in {SIDES} and shape rect|round")
    out = {"side": c["side"], "shape": c.get("shape", "rect"), "label": str(c.get("label") or f"cutout{i + 1}")}
    out["pos"] = _pos(c.get("pos"), f"cutouts[{i}].pos")
    size = c.get("size")
    out["size"] = _pos([size, size] if isinstance(size, (int, float)) else size, f"cutouts[{i}].size", positive=True)
    fu, fv = face_extent(out["side"], inner)
    (u, v), (sw, sh) = out["pos"], out["size"]
    if out["shape"] == "round":
        sh = sw
    side_wall = out["side"] not in ("top", "bottom")
    vlo, vhi = (v - sh / 2, v + sh / 2) if side_wall else (v - sh / 2 + fv / 2, v + sh / 2 + fv / 2)
    if abs(u) + sw / 2 > fu / 2 + 1e-6 or vlo < -1e-6 or vhi > fv + 1e-6:
        raise ModelError(f"cutouts[{i}] ({out['label']}) lies outside the {out['side']} wall ({fu:g} x {fv:g} mm)")
    return out


def vent_cutouts(vents: dict[str, Any], inner: list[float]) -> list[dict[str, Any]]:
    """Parallel vertical slots (rect cutouts) centred on a side: count, slot_mm = slot width."""
    side = vents.get("side")
    count = vents.get("count", 0)
    if side not in SIDES or isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= MAX_ITEMS:
        raise ModelError(f"vents needs side in {SIDES} and an integer count 1..{MAX_ITEMS}")
    slot = _num(vents, "slot_mm", 1.5, minimum=0.1)
    fu, fv = face_extent(side, inner)
    length = min(fv * 0.6, 12.0) if side not in ("top", "bottom") else min(fv * 0.6, 12.0)
    pitch = slot * 2
    v = fv / 2 if side not in ("top", "bottom") else 0.0
    return [check_cutout({"side": side, "pos": [(k - (count - 1) / 2) * pitch, v], "size": [slot, length], "label": f"vent{k + 1}"}, inner, 1000 + k)
            for k in range(count)]


def check_posts(items: Any, key: str, inner: list[float]) -> list[dict[str, Any]]:
    if items is None:
        return []
    if not isinstance(items, list) or len(items) > MAX_ITEMS:
        raise ModelError(f"{key} must be a list of at most {MAX_ITEMS} items")
    out = []
    for i, p in enumerate(items):
        if not isinstance(p, dict):
            raise ModelError(f"{key}[{i}] must be an object")
        item = {"pos": _pos(p.get("pos"), f"{key}[{i}].pos"), "height_mm": _num(p, "height_mm", 5, minimum=0.1),
                "hole_mm": _num(p, "hole_mm", 0.0 if key == "standoffs" else 2.5), "outer_mm": _num(p, "outer_mm", 6, minimum=0.1)}
        if item["hole_mm"] >= item["outer_mm"] or item["height_mm"] > inner[2]:
            raise ModelError(f"{key}[{i}]: need hole_mm < outer_mm and height_mm <= inner height")
        if abs(item["pos"][0]) + item["outer_mm"] / 2 > inner[0] / 2 or abs(item["pos"][1]) + item["outer_mm"] / 2 > inner[1] / 2:
            raise ModelError(f"{key}[{i}] lies outside the inner floor")
        out.append(item)
    return out


def fit_inner(fit: Any) -> list[float]:
    """Inner size from the bounding box of a stored model's parts (box-like extents) plus margin."""
    from app.model3d.store import ModelStore
    if not isinstance(fit, dict) or not isinstance(fit.get("model"), str):
        raise ModelError("fit_to_part needs {model, part_ids|layer, margin_mm}")
    model = ModelStore().load(fit["model"])
    ids = fit.get("part_ids")
    parts = [model.parts[i] for i in ids if i in model.parts] if ids else [p for p in model.parts.values() if p.layer == fit.get("layer")]
    if not parts or (ids and len(parts) != len(ids)):
        raise ModelError("fit_to_part matched no parts (check part_ids or layer)")
    lo, hi = [1e18] * 3, [-1e18] * 3
    for p in parts:
        s = p.scale if isinstance(p.scale, list) else [p.scale] * 3
        for a in range(3):
            lo[a], hi[a] = min(lo[a], p.pos[a] - s[a] / 2), max(hi[a], p.pos[a] + s[a] / 2)
    m = _num(fit, "margin_mm", 1.0)
    return [hi[0] - lo[0] + 2 * m, hi[2] - lo[2] + 2 * m, hi[1] - lo[1] + 2 * m]


def normalise(spec: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise ModelError("enclosure spec must be an object")
    inner = _pos(spec["inner_mm"], "inner_mm", 3, positive=True) if "inner_mm" in spec else fit_inner(spec.get("fit_to_part"))
    wall = _num(spec, "wall_mm", 2.0, minimum=0.2)
    floor = _num(spec, "floor_mm", wall, minimum=0.2)
    lid = spec.get("lid") or {}
    if not isinstance(lid, dict) or lid.get("type", "snap") not in LID_TYPES:
        raise ModelError(f"lid.type must be one of {LID_TYPES}")
    corner = _num(spec, "corner_radius_mm", 0.0)
    if corner > min(inner[0], inner[1]) / 2 + wall:
        raise ModelError("corner_radius_mm is larger than half the footprint")
    cuts = [check_cutout(c, inner, i) for i, c in enumerate(spec.get("cutouts") or [])]
    if spec.get("vents"):
        cuts += vent_cutouts(spec["vents"], inner)
    if len(cuts) > MAX_ITEMS:
        raise ModelError(f"at most {MAX_ITEMS} cutouts and vent slots")
    return {"name": str(spec.get("name") or "enclosure"), "inner": inner, "wall": wall, "floor": floor,
            "lid_type": lid.get("type", "snap"), "lid_t": _num(lid, "thickness_mm", 2.0, minimum=0.2), "corner": corner,
            "posts": check_posts(spec.get("screw_posts"), "screw_posts", inner), "standoffs": check_posts(spec.get("standoffs"), "standoffs", inner),
            "cutouts": cuts, "notes": spec.get("print_notes") if isinstance(spec.get("print_notes"), dict) else {},
            "use_csg": bool(spec.get("use_csg")), "model_id": spec.get("model_id")}
