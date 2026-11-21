# backend/app/model3d/packs/pcb/traces.py
"""Copper traces as chains of thin boxes (one group per trace) and the trace diff helper for model_propose."""

import math
import re
from collections.abc import Sequence
from typing import Any

from app.model3d.packs.pcb.layers import (
    COLOR,
    COPPER_H,
    OPACITY,
    TRACE_LAYER,
    Frame,
    part,
)
from app.model3d.packs.pcb.spec import validate, validate_trace


def net_slug(net: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.\-]", "_", net)[:40]


def trace_parts(f: Frame, tid: str, t: dict[str, Any]) -> list[dict[str, Any]]:
    """Group `tid` on the trace's copper layer plus one box per segment and a round joint per inner vertex."""
    layer = TRACE_LAYER[t["layer"]]
    w, pts = t["width_mm"], t["points"]
    props = {"kind": "trace", "net": t["net"], "layer": t["layer"], "width_mm": w, "points": pts}
    out = [part(tid, "group", layer, [0, f.layer_y(layer), 0], name=f"trace {t['net']}", props=props)]
    for j, (a, b) in enumerate(zip(pts, pts[1:], strict=False), 1):
        (ax, az), (bx, bz) = f.xz(*a), f.xz(*b)
        length = math.hypot(bx - ax, bz - az)
        angle = math.atan2(-(bz - az), bx - ax)
        out.append(part(f"{tid}_s{j}", "box", layer, [(ax + bx) / 2, 0, (az + bz) / 2], [length, COPPER_H, w], rot=[0, angle, 0],
                        color=COLOR["copper"], opacity=OPACITY["copper"], parent=tid, name=f"segment {j}"))
    for j, p in enumerate(pts[1:-1], 1):
        x, z = f.xz(*p)
        out.append(part(f"{tid}_j{j}", "cylinder", layer, [x, 0, z], [w, COPPER_H, w], color=COLOR["copper"],
                        opacity=OPACITY["copper"], parent=tid, name=f"joint {j}"))
    return out


def trace_ids(spec: dict[str, Any]) -> list[str]:
    """Part ids of the trace groups in generation order: trace_<net>_<n>."""
    counts: dict[str, int] = {}
    ids = []
    for t in spec["traces"]:
        n = counts[t["net"]] = counts.get(t["net"], 0) + 1
        ids.append(f"trace_{net_slug(t['net'])}_{n}")
    return ids


def pcb_trace_diff_helper(spec: dict[str, Any], net: str, new_points: Sequence[Sequence[float]], layer: str | None = None,
                          width_mm: float | None = None, trace_id: str | None = None) -> list[dict[str, Any]]:
    """`changes` for model_propose: remove all trace groups of `net`, add one polyline through `new_points`.

    Layer and width default to the first existing trace of the net (else top, 0.25 mm). The new group id is
    `trace_<net>_rev` unless `trace_id` is given, so it never collides with the removed ids.
    """
    s = validate(spec)
    ids = [tid for tid, t in zip(trace_ids(s), s["traces"], strict=True) if t["net"] == net]
    old = next((t for t in s["traces"] if t["net"] == net), None)
    t = validate_trace({"net": net, "layer": layer or (old["layer"] if old else "top"),
                        "width_mm": width_mm or (old["width_mm"] if old else 0.25), "points": new_points},
                       s["size"], s["layers"], f"trace diff for net {net}")
    f = Frame(s["size"], s["thickness"], s["layers"])
    new = trace_parts(f, trace_id or f"trace_{net_slug(net)}_rev", t)
    return [{"op": "remove", "id": i} for i in ids] + [{"op": "add", "part": p} for p in new]
