# backend/app/imaging/house_parse.py
"""Validate and normalise the model's house analysis JSON (tolerant of fences and sloppy types)."""

from typing import Any

from app.vision.parse import AnalysisParseError, extract_json

SIDES = ("n", "e", "s", "w")
MAX_ROOMS = 40


def _s(v: Any, limit: int = 200) -> str:
    return v.strip()[:limit] if isinstance(v, str) else ""


def _n(v: Any, low: float = 0.0, high: float = 200.0) -> float | None:
    ok = isinstance(v, (int, float)) and not isinstance(v, bool) and v == v
    return float(v) if ok and low < v <= high else None


def _conf(v: Any) -> float | None:
    return round(min(max(float(v), 0.0), 1.0), 2) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _side(v: Any) -> str | None:
    return _s(v, 2).lower()[:1] if _s(v, 2).lower()[:1] in SIDES else None


def _openings(v: Any) -> list[dict[str, Any]]:
    out = []
    for o in v if isinstance(v, list) else []:
        if isinstance(o, dict) and _side(o.get("wall")):
            out.append({"wall": _side(o.get("wall")), "offset_m": _n(o.get("offset_m"), -1e-9, 100.0), "width_m": _n(o.get("width_m"), 0.2, 6.0)})
    return out[:8]


def _room(r: Any) -> dict[str, Any] | None:
    if not isinstance(r, dict) or not _s(r.get("name"), 80):
        return None
    cands = [{"width_m": _n(c.get("width_m")), "depth_m": _n(c.get("depth_m")), "source": _s(c.get("source"), 80),
              "confidence": _conf(c.get("confidence"))} for c in r.get("dimension_candidates") or [] if isinstance(c, dict)]
    furn = [_s(f.get("kind"), 20) for f in r.get("furniture") or [] if isinstance(f, dict)]
    return {
        "name": _s(r["name"], 80), "width_m": _n(r.get("width_m")), "depth_m": _n(r.get("depth_m")),
        "dimension_source": _s(r.get("dimension_source"), 12).lower() or None, "dimension_confidence": _conf(r.get("dimension_confidence")),
        "candidates": [c for c in cands if c["width_m"] and c["depth_m"]][:6],
        "relative_to": _s(r.get("relative_to"), 80) or None, "side": _side(r.get("side")),
        "floor_material": _s(r.get("floor_material"), 60) or None, "floor_color": _s(r.get("floor_color"), 40) or None,
        "doors": _openings(r.get("doors")), "windows": _openings(r.get("windows")), "furniture": [f for f in furn if f][:10],
    }


def _storeys(v: Any) -> list[dict[str, Any]]:
    out = []
    for i, st in enumerate(v if isinstance(v, list) else []):
        if not isinstance(st, dict):
            continue
        rooms = [r for r in map(_room, st.get("rooms") or []) if r][:MAX_ROOMS]
        level = st.get("level")
        out.append({"name": _s(st.get("name"), 40) or f"Storey {i}", "level": int(level) if isinstance(level, (int, float)) and not isinstance(level, bool) else i,
                    "height_m": _n(st.get("height_m"), 1.5, 6.0), "rooms": rooms})
    return sorted((s for s in out if s["rooms"]), key=lambda s: s["level"])


def _exterior(v: Any) -> dict[str, Any]:
    v = v if isinstance(v, dict) else {}
    grid = v.get("window_grid") if isinstance(v.get("window_grid"), dict) else {}
    cols, rows = _n(grid.get("cols"), 0, 20), _n(grid.get("rows"), 0, 10)
    floors = _n(v.get("floors"), 0, 12)
    return {"roof_type": _s(v.get("roof_type"), 20).lower() or None, "roof_color": _s(v.get("roof_color"), 40) or None,
            "floors": int(floors) if floors else None, "wall_color": _s(v.get("wall_color"), 40) or None,
            "wall_material": _s(v.get("wall_material"), 60) or None,
            "window_grid": {"cols": int(cols), "rows": int(rows or 1)} if cols else None,
            "footprint_width_m": _n(v.get("footprint_width_m")), "footprint_depth_m": _n(v.get("footprint_depth_m")),
            "confidence": _conf(v.get("confidence"))}


def _texts(v: Any, n: int = 12) -> list[str]:
    return [_s(t, 300) for t in v if _s(t, 300)][:n] if isinstance(v, list) else []


def parse_house(text: str) -> dict[str, Any]:
    """The normalised analysis; AnalysisParseError (so the caller can retry once) when it has no rooms at all."""
    raw = extract_json(text)
    storeys = _storeys(raw.get("storeys"))
    if not storeys:
        raise AnalysisParseError("storeys must list at least one storey with named rooms")
    conf_raw = raw.get("confidence")
    conf: dict[str, Any] = conf_raw if isinstance(conf_raw, dict) else {}
    interior = [{"room": _s(p.get("room"), 80), "floor_material": _s(p.get("floor_material"), 60) or None,
                 "wall_color": _s(p.get("wall_color"), 40) or None,
                 "furniture": _texts(p.get("furniture"), 10)} for p in raw.get("interior_photos") or [] if isinstance(p, dict) and _s(p.get("room"), 80)]
    return {"summary": _s(raw.get("summary"), 800), "storeys": storeys, "exterior": _exterior(raw.get("exterior")),
            "interior_photos": interior, "scale_hints": _texts(raw.get("scale_hints")), "conflicts": _texts(raw.get("conflicts")),
            "confidence": {k: _conf(conf.get(k)) for k in ("overall", "rooms", "exterior")},
            "open_questions": _texts(raw.get("open_questions"), 10)}


def parse_refine(text: str) -> dict[str, Any]:
    raw = extract_json(text)
    obs = []
    for o in raw.get("observations") or []:
        if isinstance(o, dict) and _s(o.get("room"), 80):
            obs.append({"room": _s(o["room"], 80), "floor_color": _s(o.get("floor_color"), 40) or None,
                        "floor_material": _s(o.get("floor_material"), 60) or None, "confidence": _conf(o.get("confidence")),
                        "furniture": [_s(f.get("kind"), 20) for f in o.get("furniture") or [] if isinstance(f, dict) and _s(f.get("kind"), 20)][:10]})
    if "observations" not in raw:
        raise AnalysisParseError("observations is missing")
    return {"observations": obs, "unmatched": _texts(raw.get("unmatched")), "open_questions": _texts(raw.get("open_questions"), 10)}
