# backend/app/imaging/spec_layout.py
"""Room sizes and plan positions for one storey of the house analysis (metres, plan x east, y south)."""

from typing import Any

from app.model3d.packs.building.plan import DEFAULT_ROOM
from app.model3d.packs.building.spec import slug

CONFLICT_RATIO = 0.12  # candidates differing by more than this relative amount are reported as a conflict
EPS = 0.01


def room_size(room: dict[str, Any], notes: dict[str, list[str]]) -> tuple[float, float, bool]:
    """(width, depth, estimated). Stated sizes win; else the most confident candidate; else the 3.5 x 4 m default."""
    name = room["name"]
    w, d = room.get("width_m"), room.get("depth_m")
    cands = sorted(room.get("candidates") or [], key=lambda c: -(c["confidence"] or 0))
    if cands:
        best = cands[0]
        w, d = w or best["width_m"], d or best["depth_m"]
        for other in cands[1:]:
            if abs(other["width_m"] - w) > CONFLICT_RATIO * w or abs(other["depth_m"] - d) > CONFLICT_RATIO * d:
                notes["conflicts"].append(
                    f"{name}: {best['width_m']} x {best['depth_m']} m ({best['source']}) vs {other['width_m']} x {other['depth_m']} m ({other['source']}); used the first")
    if w and d:
        return float(w), float(d), room.get("dimension_source") == "estimate"
    notes["questions"].append(f"What are the dimensions of '{name}'? Assumed {DEFAULT_ROOM[0]} x {DEFAULT_ROOM[1]} m.")
    return DEFAULT_ROOM[0], DEFAULT_ROOM[1], True


def _overlaps(r: list[float], placed: list[list[float]]) -> bool:
    return any(r[0] < p[0] + p[2] - EPS and p[0] < r[0] + r[2] - EPS and r[1] < p[1] + p[3] - EPS and p[1] < r[1] + r[3] - EPS for p in placed)


def _anchored(room: dict[str, Any], size: tuple[float, float], by_name: dict[str, list[float]]) -> list[float] | None:
    ref = by_name.get(str(room.get("relative_to") or "").lower())
    side = room.get("side")
    if ref is None or side is None:
        return None
    w, d = size
    x, y = {"n": (ref[0], ref[1] - d), "s": (ref[0], ref[1] + ref[3]), "e": (ref[0] + ref[2], ref[1]), "w": (ref[0] - w, ref[1])}[side]
    return [x, y, w, d]


def layout_storey(rooms: list[dict[str, Any]], notes: dict[str, list[str]], used_ids: set[str]) -> list[dict[str, Any]]:
    """Rooms with `rect` [x, y, w, d] and a unique `id`, moved so the plan starts at 0, 0.

    A room is put next to the room it names in `relative_to` on `side`; when that is missing or would overlap
    another room it goes to the east of everything placed so far (and the user is asked).
    `used_ids` holds the room ids of the whole building (they must be unique across storeys)."""
    placed: list[list[float]] = []
    by_name: dict[str, list[float]] = {}
    out: list[dict[str, Any]] = []
    for room in rooms:
        w, d, estimated = room_size(room, notes)
        rect = _anchored(room, (w, d), by_name)
        if rect is None or _overlaps(rect, placed):
            if rect is not None or (room.get("relative_to") and placed):
                notes["questions"].append(f"Where exactly is '{room['name']}' relative to '{room.get('relative_to')}'? Placed beside the other rooms.")
            rect = [max((p[0] + p[2] for p in placed), default=0.0), min((p[1] for p in placed), default=0.0), w, d]
        placed.append(rect)
        by_name[room["name"].lower()] = rect
        rid = base = slug(room["name"], f"room{len(out) + 1}")
        n = 2
        while rid in used_ids:
            rid, n = f"{base}-{n}", n + 1
        used_ids.add(rid)
        out.append({**room, "id": rid, "rect": rect, "estimated": estimated})
    x0, y0 = min(r[0] for r in placed), min(r[1] for r in placed)
    for o in out:
        o["rect"] = [round(o["rect"][0] - x0, 3), round(o["rect"][1] - y0, 3), round(o["rect"][2], 3), round(o["rect"][3], 3)]
    return out
