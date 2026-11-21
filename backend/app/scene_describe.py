# backend/app/scene_describe.py
"""Compact text rendering of the scene tree for the model (used by the scene_get tool)."""


def _num(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _vec(v: list) -> str:
    return "(" + ",".join(_num(x) for x in v) + ")"


def _line(o: dict, depth: int, selected: set[str]) -> str:
    parts = [("*" if o["id"] in selected else "") + o["id"], o["kind"]]
    if "pos" in o:
        parts.append("pos" + _vec(o["pos"]))
    if "scale" in o:
        parts.append("scale" + (_vec(o["scale"]) if isinstance(o["scale"], list) else _num(o["scale"])))
    if "color" in o:
        parts.append(o["color"])
    if isinstance(o.get("ref"), dict):
        parts.append(f"ref={o['ref']['type']}:{o['ref']['id']}")
    if o["kind"] == "entity":
        parts.append(f"{o.get('shape')} \"{str(o.get('title', ''))[:40]}\"")
    if o["kind"] == "link":
        parts.append(f"{o.get('from')}->{o.get('to')}")
    if o.get("label"):
        parts.append(f'"{o["label"]}"')
    if o["kind"] in ("text", "label") and o.get("text"):
        parts.append(f'text="{str(o["text"])[:40]}"')
    if o.get("anim"):
        anims = o["anim"] if isinstance(o["anim"], list) else [o["anim"]]
        parts.append("anim=" + "+".join(a["type"] for a in anims))
    return "  " * depth + " ".join(parts)


def describe_scene(objs: dict[str, dict], selected: list[str], camera: dict | None, explode: float, max_lines: int) -> str:
    children: dict[str | None, list[dict]] = {}
    for o in objs.values():
        parent = o.get("parent") if o.get("parent") in objs else None
        children.setdefault(parent, []).append(o)
    sel = set(selected)
    head = f"scene: {len(objs)} objects; selected: {', '.join(selected) or 'none'}"
    if explode:
        head += f"; explode={_num(explode)}"
    if camera:
        head += f"; camera pos{_vec(camera['pos'])} look{_vec(camera['look'])}"
    lines = [head]
    seen: set[str] = set()

    def walk(parent: str | None, depth: int) -> None:
        for o in children.get(parent, []):
            if o["id"] in seen:
                continue
            seen.add(o["id"])
            lines.append(_line(o, depth, sel))
            walk(o["id"], depth + 1)

    walk(None, 0)
    if len(lines) > max_lines:
        extra = len(lines) - max_lines
        lines = lines[:max_lines] + [f"... {extra} more objects"]
    return "\n".join(lines)
