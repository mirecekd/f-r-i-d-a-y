# backend/app/model3d/packs/building/openings.py
"""Resolve door and window specs onto wall segments and build their inset frame/leaf/glass boxes."""

import itertools
import math
from typing import Any

from app.model3d.packs.building.geom import TOL, edges, seg_param
from app.model3d.packs.building.parts import box, group
from app.model3d.packs.building.spec import BuildingSpecError, num
from app.model3d.packs.building.walls import yaw

KINDS = {"door": {"width": 0.9, "height": 2.05, "sill": 0.0}, "window": {"width": 1.2, "height": 1.2, "sill": 0.9}}
SIDES = {"n": 0, "e": 1, "s": 2, "w": 3}  # rect rooms: edge index of top, right, bottom, left
FRAME = 0.05
FRAME_COLOR = "#f5f5f5"
DOOR_COLOR = "#8b5a2b"
GLASS_COLOR = "#9fd8ff"


def edge_index(spec: dict[str, Any]) -> Any:
    """Room edge index named by `side` (n|e|s|w, rect rooms) or `edge`; None when neither is given."""
    side = spec.get("side")
    return SIDES[side] if isinstance(side, str) and side in SIDES else spec.get("edge")


def resolve(storey: dict[str, Any], walls: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Map wall id to its openings (sorted by offset), each with offset/width/height/sill validated to fit."""
    by_wall: dict[str, list[dict[str, Any]]] = {w["id"]: [] for w in walls}
    for i, spec in enumerate(storey["openings"]):
        what = f"openings[{i}]"
        if not isinstance(spec, dict) or spec.get("kind") not in KINDS:
            raise BuildingSpecError(f"{what}.kind must be one of {sorted(KINDS)}")
        d = KINDS[spec["kind"]]
        o = {"id": str(spec.get("id") or f"o{i + 1}"), "kind": spec["kind"], "width": num(spec.get("width", d["width"]), what, 0.1),
             "height": num(spec.get("height", d["height"]), what, 0.1), "sill": num(spec.get("sill", d["sill"]), what, 0.0)}
        wall = _locate(spec, o, storey, walls, what)
        if o["sill"] + o["height"] > wall["height"] + 1e-6:
            raise BuildingSpecError(f"{what} is taller than its wall ({wall['height']} m)")
        by_wall[wall["id"]].append(o)
    for wid, items in by_wall.items():
        items.sort(key=lambda o: o["offset"])
        for p, q in itertools.pairwise(items):
            if q["offset"] < p["offset"] + p["width"] - 1e-6:
                raise BuildingSpecError(f"openings {p['id']} and {q['id']} overlap on wall {wid}")
    return by_wall


def _locate(spec: dict[str, Any], o: dict[str, Any], storey: dict[str, Any], walls: list[dict[str, Any]], what: str) -> dict[str, Any]:
    offset = num(spec.get("offset", 0.0), f"{what}.offset", 0.0)
    if "wall" in spec:
        wall = next((w for w in walls if w["id"] == spec["wall"]), None)
        if wall is None:
            raise BuildingSpecError(f"{what}: unknown wall '{spec['wall']}'; walls: {[w['id'] for w in walls]}")
        if offset + o["width"] > wall["length"] + 1e-6:
            raise BuildingSpecError(f"{what} ({offset}+{o['width']} m) does not fit wall {wall['id']} of {wall['length']:.2f} m")
        o["offset"] = offset
        return wall
    room = next((r for r in storey["rooms"] if r["id"] == spec.get("room")), None)
    if room is None:
        raise BuildingSpecError(f"{what} needs 'wall' or a known 'room' (got {spec.get('room')!r})")
    edge = edge_index(spec)
    ring = edges(room["polygon"])
    if not isinstance(edge, int) or isinstance(edge, bool) or not 0 <= edge < len(ring):
        raise BuildingSpecError(f"{what} with a room needs side n|e|s|w (rect rooms) or edge 0..{len(ring) - 1}")
    a, b = ring[edge]
    length = math.dist(a, b)
    p0 = [a[0] + (b[0] - a[0]) * offset / length, a[1] + (b[1] - a[1]) * offset / length]
    p1 = [a[0] + (b[0] - a[0]) * (offset + o["width"]) / length, a[1] + (b[1] - a[1]) * (offset + o["width"]) / length]
    for w in walls:
        (t0, d0), (t1, d1) = seg_param(p0, w["a"], w["b"]), seg_param(p1, w["a"], w["b"])
        eps = TOL / max(w["length"], 1e-9)
        if d0 <= 0.01 and d1 <= 0.01 and -eps <= min(t0, t1) and max(t0, t1) <= 1 + eps:
            o["offset"] = max(0.0, min(t0, t1) * w["length"])
            return w
    raise BuildingSpecError(f"{what} on room '{room['id']}' edge {edge} does not fit inside a single wall")


def opening_parts(w: dict[str, Any], o: dict[str, Any], pid: str, parent: str, layer: str, props: dict[str, Any]) -> list[dict[str, Any]]:
    """Frame, leaf (door) or glass (window) boxes, inset in the wall plane; the group sits at the opening centre."""
    a, b, t = w["a"], w["b"], w["thickness"]
    k = (o["offset"] + o["width"] / 2) / w["length"]
    pos = [a[0] + (b[0] - a[0]) * k, o["sill"] + o["height"] / 2, a[1] + (b[1] - a[1]) * k]
    p = {**props, "opening": o["kind"], "wall": w["id"], "width": o["width"], "height": o["height"], "sill": o["sill"]}
    out = [group(pid, f"{o['kind']} {o['id']}", pos, layer, parent, [0.0, yaw(a, b), 0.0], p)]
    wd, ht, depth = o["width"], o["height"], t + 0.04
    for name, c, s in (("jamb_l", [-(wd - FRAME) / 2, 0, 0], [FRAME, ht, depth]), ("jamb_r", [(wd - FRAME) / 2, 0, 0], [FRAME, ht, depth]),
                       ("head", [0, (ht - FRAME) / 2, 0], [wd, FRAME, depth])):
        out.append(box(f"{pid}-{name}", name, c, s, layer, FRAME_COLOR, pid, props=p))
    inner_w, inner_h = wd - 2 * FRAME, ht - FRAME
    if o["kind"] == "door":
        out.append(box(f"{pid}-leaf", "door leaf", [0, -FRAME / 2, 0], [inner_w, inner_h, 0.04], layer, DOOR_COLOR, pid, props=p))
        out.append(box(f"{pid}-handle", "handle", [inner_w / 2 - 0.1, -FRAME / 2, 0.04], [0.12, 0.03, 0.04], layer, "#c8c8c8", pid, props=p))
    else:
        out.append(box(f"{pid}-glass", "glass", [0, -FRAME / 2, 0], [inner_w, inner_h, 0.02], layer, GLASS_COLOR, pid, opacity=0.45, props=p))
        out.append(box(f"{pid}-mullion", "mullion", [0, -FRAME / 2, 0], [0.03, inner_h, 0.04], layer, FRAME_COLOR, pid, props=p))
        out.append(box(f"{pid}-ledge", "sill", [0, -(ht + 0.04) / 2, 0.05], [wd + 0.1, 0.04, depth + 0.08], layer, FRAME_COLOR, pid, props=p))
    return out
