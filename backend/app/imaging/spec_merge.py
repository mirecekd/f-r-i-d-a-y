# backend/app/imaging/spec_merge.py
"""Map the normalised house analysis onto a `building` pack spec (extended plan_to_spec for several sources)."""

from typing import Any

from app.imaging.colors import to_hex
from app.imaging.spec_layout import layout_storey
from app.model3d.packs.building.build import building_from_spec
from app.model3d.packs.building.spec import STOREY_HEIGHT, BuildingSpecError

ROOF_BY_NAME = {"gable": "gable", "hip": "gable", "pitched": "gable", "flat": "flat"}


def _openings(room: dict[str, Any]) -> list[dict[str, Any]]:
    """Door and window specs of one laid-out room; a missing offset centres the opening on its wall."""
    x, y, w, d = room["rect"]
    out: list[dict[str, Any]] = []
    for kind, items in (("door", room["doors"]), ("window", room["windows"])):
        for i, o in enumerate(items):
            length = w if o["wall"] in ("n", "s") else d
            width = o["width_m"] or (0.9 if kind == "door" else 1.2)
            if width > length - 0.2:
                continue
            offset = o["offset_m"] if o["offset_m"] is not None else (length - width) / 2
            offset = min(max(offset, 0.05), length - width - 0.05)
            out.append({"id": f"{room['id']}-{kind[0]}{i + 1}", "room": room["id"], "side": o["wall"], "kind": kind,
                        "offset": round(offset, 3), "width": width})
    return out


def _grid_windows(storey_rooms: list[dict[str, Any]], cols: int) -> list[dict[str, Any]]:
    """Spread `cols` windows over the south facade rooms that have no south window of their own."""
    front = max(r["rect"][1] + r["rect"][3] for r in storey_rooms)
    row = [r for r in storey_rooms if abs(r["rect"][1] + r["rect"][3] - front) < 0.02 and not any(o["wall"] == "s" for o in r["windows"])]
    total = sum(r["rect"][2] for r in row) or 1.0
    out = []
    for r in row:
        n = max(1, round(cols * r["rect"][2] / total)) if cols > 1 else (1 if r is row[0] else 0)
        slot = r["rect"][2] / max(n, 1)
        for k in range(n):
            if slot >= 1.5:
                out.append({"id": f"{r['id']}-gw{k + 1}", "room": r["id"], "side": "s", "kind": "window",
                            "offset": round(k * slot + (slot - 1.2) / 2, 3), "width": 1.2})
    return out


def _storey(st: dict[str, Any], notes: dict[str, list[str]], grid_cols: int | None, used_ids: set[str]) -> dict[str, Any]:
    rooms = layout_storey(st["rooms"], notes, used_ids)
    openings = [o for r in rooms for o in _openings(r)]
    if grid_cols:
        openings += _grid_windows(rooms, grid_cols)
    return {"name": st["name"], "height": st["height_m"] or STOREY_HEIGHT,
            "rooms": [{"id": r["id"], "name": r["name"], "rect": r["rect"], **({"floor_color": c} if (c := to_hex(r["floor_color"] or r["floor_material"])) else {})}
                      for r in rooms],
            "openings": openings, "furniture": [{"kind": k, "room": r["id"]} for r in rooms for k in r["furniture"] if k in _KINDS]}


_KINDS = ("bed", "sofa", "table", "chair", "wardrobe", "desk", "kitchen_unit", "generic")


def _repeat_upper(ground: dict[str, Any], level: int) -> dict[str, Any]:
    """A copy of `ground` as an upper storey: no openings or furniture, room ids made unique."""
    name = "Upper floor" if level == 1 else f"Upper floor {level}"
    rooms = [{**r, "id": f"{r['id']}-u{level}", "name": f"{r['name']} (upper)"} for r in ground["rooms"]]
    return {"name": name, "height": ground["height"], "rooms": rooms, "openings": [], "furniture": []}


def merge_to_spec(analysis: dict[str, Any]) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """(building spec, {'conflicts': [...], 'questions': [...]}); the spec always builds (openings are dropped when they cannot)."""
    notes: dict[str, list[str]] = {"conflicts": list(analysis["conflicts"]), "questions": list(analysis["open_questions"])}
    ext = analysis["exterior"]
    cols = (ext["window_grid"] or {}).get("cols")
    used_ids: set[str] = set()
    storeys = [_storey(st, notes, cols if i == 0 else None, used_ids) for i, st in enumerate(analysis["storeys"])]
    floors = ext["floors"] or 1
    if len(storeys) == 1 and floors > 1:
        storeys += [_repeat_upper(storeys[0], level) for level in range(1, floors)]
        notes["questions"].append("The plans show one storey but the outside photos show more: the upper floors repeat the ground floor layout. Is that right?")
    spec: dict[str, Any] = {"name": "house", "units": "m", "storeys": storeys,
                            "roof": {"type": ROOF_BY_NAME.get(ext["roof_type"] or "gable", "gable"), "overhang": 0.4,
                                     **({"color": c} if (c := to_hex(ext["roof_color"])) else {})}}
    if c := to_hex(ext["wall_color"] or ext["wall_material"]):
        spec["wall_color"] = c
    _scale_to_footprint(spec, ext, analysis, notes)
    _keep_fitting_openings(spec, notes)
    return spec, notes


def _fits(spec: dict[str, Any]) -> bool:
    try:
        building_from_spec(spec)
    except BuildingSpecError:
        return False
    return True


def _keep_fitting_openings(spec: dict[str, Any], notes: dict[str, list[str]]) -> None:
    """Keep each door and window one by one and drop those the walls cannot take (shared walls, overlaps)."""
    dropped: list[str] = []
    for st in spec["storeys"]:
        wanted, st["openings"] = st["openings"], []
        for o in wanted:
            st["openings"].append(o)
            if not _fits(spec):
                st["openings"].pop()
                dropped.append(o["id"])
    if dropped:
        notes["questions"].append(f"These doors/windows did not fit the walls and were left out: {', '.join(dropped[:8])}. Where exactly are they?")


def _scale_to_footprint(spec: dict[str, Any], ext: dict[str, Any], analysis: dict[str, Any], notes: dict[str, list[str]]) -> None:
    """With no stated room size anywhere, stretch the layout to the footprint seen from outside; else say the scale is a guess."""
    stated = any(r["width_m"] or r["candidates"] for s in analysis["storeys"] for r in s["rooms"])
    if stated:
        return
    rects = [r["rect"] for s in spec["storeys"] for r in s["rooms"]]
    w, d = max(r[0] + r[2] for r in rects), max(r[1] + r[3] for r in rects)
    fw, fd = ext["footprint_width_m"], ext["footprint_depth_m"]
    if not (fw and fd):
        notes["questions"].append("No dimensions or scale were found on the plans: all sizes are guesses. What is the real size of one room?")
        return
    sx, sy = fw / w, fd / d
    for s in spec["storeys"]:
        for r in s["rooms"]:
            x, y, rw, rd = r["rect"]
            r["rect"] = [round(x * sx, 3), round(y * sy, 3), round(rw * sx, 3), round(rd * sy, 3)]
        s["openings"] = []
    notes["questions"].append("Room sizes come from the footprint seen in the outside photo only; please confirm real dimensions.")
