# backend/app/model3d/packs/pcb/board.py
"""Board substrate, solder mask, inner planes, vias, silkscreen and edge outline parts."""

from typing import Any

from app.model3d.packs.pcb.layers import (
    COLOR,
    COPPER_H,
    MASK_H,
    OPACITY,
    Frame,
    box,
    cyl,
    part,
)


def board_parts(f: Frame, spec: dict[str, Any]) -> list[dict[str, Any]]:
    out = [box("board", "board", 0, 0, -f.t / 2, f.w, f.h, f.t, color=COLOR["board"], opacity=OPACITY["board"],
               name=spec["name"], props={"name": spec["name"], "size_mm": [f.w, f.h], "thickness_mm": f.t, "layers": f.layers}),
           box("mask_top", "mask_top", 0, 0, f.top, f.w, f.h, MASK_H, color=COLOR["mask"], opacity=OPACITY["mask"], name="solder mask")]
    if f.layers == 4:
        for name in ("inner1", "inner2"):
            y = f.layer_y(name)
            out.append(box(f"plane_{name}", name, 0, 0, y - COPPER_H / 2, f.w - 0.6, f.h - 0.6, COPPER_H,
                           color=COLOR["plane"], opacity=OPACITY["plane"], name=f"{name} plane", props={"net": "plane"}))
    if spec["outline"]:
        pts = [[x, f.top + MASK_H + 0.01, z] for x, z in (f.xz(*p) for p in spec["outline"])]
        out.append(part("edge_outline", "polyline", "board", [0, 0, 0], color="#ffd35a", geom={"pts": pts, "closed": True}, name="board outline"))
    return out


def via_parts(f: Frame, spec: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, v in enumerate(spec["vias"], 1):
        x, z = f.xz(*v["pos"])
        d = v["drill_mm"]
        props = {"net": v["net"], "drill_mm": d, "kind": "via"}
        out.append(part(f"via{i}", "group", "vias", [x, 0, z], name=f"via {v['net'] or i}", props=props))
        out.append(cyl(f"via{i}_barrel", "vias", 0, 0, -f.t / 2 - 0.02, d + 0.45, f.t + 0.04, color=COLOR["via"], parent=f"via{i}",
                       opacity=1.0, name="barrel"))
        for tag, y in (("top", f.top + MASK_H + 0.005), ("bot", -f.top - 0.04)):
            out.append(cyl(f"via{i}_hole_{tag}", "vias", 0, 0, y - 0.0, d, 0.035, color="#101010", parent=f"via{i}", name=f"hole {tag}"))
    return out


def silk_parts(f: Frame, spec: dict[str, Any], comps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    texts = list(spec["silk"])
    if spec["silk_refs"]:
        texts += [{"text": c["ref"], "pos": [c["pos"][0], c["pos"][1] + 2.2], "size": 1.0} for c in comps if c["side"] == "top"]
    out = []
    for i, s in enumerate(texts, 1):
        x, z = f.xz(*s["pos"])
        out.append(part(f"silk{i}", "text", "silk_top", [x, f.top + MASK_H + 0.3, z], color=COLOR["silk"], name=f"silk {s['text']}",
                        geom={"text": s["text"], "size": s["size"]}))
    return out
