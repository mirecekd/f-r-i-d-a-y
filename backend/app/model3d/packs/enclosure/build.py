# backend/app/model3d/packs/enclosure/build.py
"""Part dicts for an enclosure from a normalised spec. Origin: footprint centre, y up, case bottom at y=0.
front = +z, back = -z, right = +x, left = -x. Cutters are `tool` boxes/cylinders tagged cutter with props.subtract_from."""

import math
import re
from typing import Any

LAYERS = {"case": {"z_index": 0, "color": "#4fd8ff", "opacity": 0.55}, "posts": {"z_index": 1, "color": "#ffb347"},
          "lid": {"z_index": 2, "color": "#7dffb0", "opacity": 0.55}, "cutters": {"z_index": 3, "color": "#05070a", "opacity": 0.7}}
CUT_COLOR = "#05070a"


def apply_layers(model: Any) -> None:
    """Set the pack's layer order/colours on a Model so that layer explode stacks case, posts, lid, cutters."""
    for name, lay in LAYERS.items():
        model.layers.setdefault(name, dict(lay))


def _box(pid: str, pos: list[float], size: list[float], layer: str, parent: str | None, **extra: Any) -> dict[str, Any]:
    return {"id": pid, "kind": "box", "name": pid, "parent": parent, "pos": [round(v, 4) for v in pos], "scale": [round(v, 4) for v in size], "layer": layer, **extra}


def _slug(label: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", label).strip("_")[:40] or "cut"


def _cutter(c: dict[str, Any], s: dict[str, Any], pid: str) -> tuple[dict[str, Any], str]:
    """One cutter part and the id of the part it is subtracted from."""
    w, d, h = s["inner"]
    wall, floor, side = s["wall"], s["floor"], c["side"]
    u, v = c["pos"]
    sw, sh = c["size"]
    if c["shape"] == "round":
        sh = sw
    depth = (s["lid_t"] if side == "top" else floor if side == "bottom" else wall) + 1.0
    top_y = floor + h
    spot = {"front": ([u, floor + v, d / 2 + wall / 2], [sw, sh, depth]), "back": ([-u, floor + v, -d / 2 - wall / 2], [sw, sh, depth]),
            "right": ([w / 2 + wall / 2, floor + v, u], [depth, sh, sw]), "left": ([-w / 2 - wall / 2, floor + v, -u], [depth, sh, sw]),
            "top": ([u, top_y + s["lid_t"] / 2, v], [sw, depth, sh]), "bottom": ([u, floor / 2, v], [sw, depth, sh])}[side]
    target = "lid" if side == "top" else "shell"
    part = _box(pid, spot[0], spot[1], "cutters", target, color=CUT_COLOR, tags=["cutter"],
                props={"subtract_from": target, "side": side, "label": c["label"], "shape": c["shape"], "size_mm": [sw, sh]})
    if c["shape"] == "round":
        part["kind"] = "cylinder"
        part["rot"] = {"front": [math.pi / 2, 0, 0], "back": [math.pi / 2, 0, 0], "left": [0, 0, math.pi / 2], "right": [0, 0, math.pi / 2]}.get(side, [0, 0, 0])
        part["scale"] = [sw, depth, sw]
    return part, target


def _shell(s: dict[str, Any]) -> list[dict[str, Any]]:
    w, d, h = s["inner"]
    wall, floor = s["wall"], s["floor"]
    ow, od = w + 2 * wall, d + 2 * wall
    return [
        {"id": "shell", "kind": "group", "name": s["name"] + " case", "layer": "case"},
        _box("floor", [0, floor / 2, 0], [ow, floor, od], "case", "shell"),
        _box("wall_front", [0, floor + h / 2, d / 2 + wall / 2], [ow, h, wall], "case", "shell"),
        _box("wall_back", [0, floor + h / 2, -d / 2 - wall / 2], [ow, h, wall], "case", "shell"),
        _box("wall_right", [w / 2 + wall / 2, floor + h / 2, 0], [wall, h, d], "case", "shell"),
        _box("wall_left", [-w / 2 - wall / 2, floor + h / 2, 0], [wall, h, d], "case", "shell"),
    ]


def _lid(s: dict[str, Any]) -> list[dict[str, Any]]:
    w, d, h = s["inner"]
    wall, floor, t = s["wall"], s["floor"], s["lid_t"]
    y = floor + h + t / 2
    parts = [{"id": "lid", "kind": "group", "name": s["name"] + " lid", "layer": "lid", "props": {"lid_type": s["lid_type"]}},
             _box("lid_plate", [0, y, 0], [w + 2 * wall, t, d + 2 * wall], "lid", "lid")]
    if s["lid_type"] == "snap":  # four thin lip walls that sit inside the case
        lip, lh, y0 = 1.2, 2.0, floor + h - 1.0
        for pid, pos, size in (("lip_front", [0, y0, d / 2 - lip / 2 - 0.2], [w - 0.4, lh, lip]), ("lip_back", [0, y0, -d / 2 + lip / 2 + 0.2], [w - 0.4, lh, lip]),
                               ("lip_right", [w / 2 - lip / 2 - 0.2, y0, 0], [lip, lh, d - 2 * lip - 0.8]), ("lip_left", [-w / 2 + lip / 2 + 0.2, y0, 0], [lip, lh, d - 2 * lip - 0.8])):
            parts.append(_box(pid, pos, size, "lid", "lid"))
    elif s["lid_type"] == "screw":  # four screw ears at the corners
        for i, (sx, sz) in enumerate(((1, 1), (1, -1), (-1, 1), (-1, -1))):
            parts.append({"id": f"lid_screw{i + 1}", "kind": "cylinder", "name": f"lid screw {i + 1}", "parent": "lid", "layer": "lid",
                          "pos": [sx * (w / 2 - 3), y + t / 2 + 0.4, sz * (d / 2 - 3)], "scale": [4, 0.8, 4], "color": "#d0d8e0"})
    return parts


def _posts(s: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    parts: list[dict[str, Any]] = []
    cutters: list[dict[str, Any]] = []
    items = [("post", p) for p in s["posts"]] + [("standoff", p) for p in s["standoffs"]]
    if items:
        parts.append({"id": "posts", "kind": "group", "name": "posts", "layer": "posts"})
    for i, (kind, p) in enumerate(items):
        pid = f"{kind}{i + 1}"
        parts.append({"id": pid, "kind": "cylinder", "name": pid, "parent": "posts", "layer": "posts", "tags": [kind],
                      "pos": [p["pos"][0], s["floor"] + p["height_mm"] / 2, p["pos"][1]], "scale": [p["outer_mm"], p["height_mm"], p["outer_mm"]],
                      "props": {"hole_mm": p["hole_mm"], "height_mm": p["height_mm"]}})
        if p["hole_mm"] > 0:
            cutters.append({"id": f"hole_{pid}", "kind": "cylinder", "name": f"hole {pid}", "parent": pid, "layer": "cutters", "tags": ["cutter"], "color": CUT_COLOR,
                            "pos": [0, 0, 0], "scale": [p["hole_mm"] / p["outer_mm"], 1.02, p["hole_mm"] / p["outer_mm"]],
                            "props": {"subtract_from": pid, "label": f"{pid} hole"}})
    return parts, cutters


def csg_parts(parts: list[dict[str, Any]], model_id: str) -> list[dict[str, Any]]:
    """One csg part per target that has cutters; operands are referenced by scene id (m:<model>:<part>)."""
    sid = lambda pid: f"m:{model_id}:{pid}"  # noqa: E731
    by_target: dict[str, list[str]] = {}
    for p in parts:
        if "cutter" in p.get("tags", []):
            by_target.setdefault(p["props"]["subtract_from"], []).append(p["id"])
    return [{"id": f"csg_{t}", "kind": "csg", "name": f"{t} with cut-outs", "layer": "case", "geom": {"op": "subtract", "a": sid(t), "b": [sid(c) for c in cs], "hide_inputs": True}}
            for t, cs in by_target.items()]


def build_parts(s: dict[str, Any]) -> list[dict[str, Any]]:
    parts = _shell(s) + _lid(s)
    post_parts, hole_cutters = _posts(s)
    parts += post_parts
    cutters = [_cutter(c, s, f"cut_{i + 1}_{_slug(c['label'])}") for i, c in enumerate(s["cutouts"])]
    for part, _ in cutters:
        parts.append(part)
    parts += hole_cutters
    for p in parts:
        p.setdefault("props", {})
        p["props"].setdefault("enclosure", s["name"])
    if s["use_csg"]:
        parts += csg_parts(parts, s["model_id"])
    return parts
