# backend/app/model3d/packs/pcb/assemble.py
"""Place component bodies on the board: component group, child body parts and top-level copper pads."""

import math
from typing import Any

from app.model3d.packs.pcb.layers import (
    COLOR,
    MASK_H,
    OPACITY,
    PAD_H,
    Frame,
    part,
    rot2,
)
from app.model3d.packs.pcb.library import build_body


def component_parts(f: Frame, c: dict[str, Any]) -> list[dict[str, Any]]:
    """Component group `comp_<ref>` (carries ref/value/footprint/nets), its body children and pad parts `pad_<ref>_<pin>`."""
    ref, bottom = c["ref"], c["side"] == "bottom"
    body = build_body(c, f"comp_{ref}")
    layer = "components_bottom" if bottom else "components"
    meta = {"ref": ref, "value": c.get("value", ""), "footprint": c.get("footprint", ""), "kind": c["kind"], "side": c["side"]}
    nets = c.get("nets") or {}
    if nets:
        meta["nets"] = nets
        meta["net"] = ",".join(sorted(set(map(str, nets.values()))))
    theta = c["rot"]
    x, z = f.xz(*c["pos"])
    y = -(f.top + MASK_H) if bottom else f.top + MASK_H
    group = part(body.pid, "group", layer, [x, y, z], rot=[math.pi if bottom else 0, math.radians(theta), 0], name=ref, props=meta)
    out = [group]
    for p in body.parts:
        p["layer"] = layer
        p["props"] = {"ref": ref, "value": meta["value"], "footprint": meta["footprint"]}
        out.append(p)
    cu = "copper_bottom" if bottom else "copper_top"
    for pad in body.pads:
        px, py = rot2(pad.x, pad.y, theta)
        py = -py if bottom else py
        wx, wz = f.xz(c["pos"][0] + px, c["pos"][1] + py)
        net = nets.get(pad.pin) or nets.get(str(pad.pin))
        props = {"ref": ref, "pin": pad.pin, "value": meta["value"], "footprint": meta["footprint"]}
        if net:
            props["net"] = str(net)
        out.append(part(f"pad_{ref}_{pad.pin}", "box", cu, [wx, f.layer_y(cu), wz], [pad.sx, PAD_H, pad.sy],
                        rot=[0, math.radians(-theta if bottom else theta), 0], color=COLOR["pad"], opacity=OPACITY["copper"],
                        name=f"{ref}.{pad.pin}", props=props))
    return out
