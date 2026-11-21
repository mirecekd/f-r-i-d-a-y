# backend/app/workshop/expand.py
"""expand(spec): validate a part-tree spec and turn it into model3d Part dicts (see model3d/model.py Part.from_dict)."""

import math
from dataclasses import dataclass, field
from typing import Any

from app.workshop.builders import KIND_KEYS, build
from app.workshop.expr import SpecError, did_you_mean
from app.workshop.instance import MAX_PARTS, instances, size
from app.workshop.params import param_env, read_params
from app.workshop.reader import Node, Reader, check_keys, join
from app.workshop.xform import clean

UNITS = ("mm", "cm", "m")
MAX_DEPTH, MAX_ARRAY = 6, 200
TOP_KEYS = {"name", "units", "params", "parts"}
COMMON_KEYS = {"id", "kind", "name", "pos", "rot", "color", "material", "parent", "tags", "mirror", "array"}
ARRAY_KEYS = {"linear": {"type", "count", "step"}, "radial": {"type", "count", "axis", "radius", "start_deg"}}
MATERIAL_KEYS = {"metal", "rough", "opacity"}


@dataclass
class Expanded:
    parts: list[dict[str, Any]] = field(default_factory=list)
    params: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _array(r: Reader) -> dict[str, Any] | None:
    raw = r.raw.get("array")
    if raw is None:
        return None
    a = Reader(raw, r.at("array"), r.env)
    kind = raw.get("type")
    if kind not in ARRAY_KEYS:
        raise SpecError(f"{a.at('type')}: expected 'linear' or 'radial'")
    check_keys(raw, ARRAY_KEYS[kind], a.path)
    count = int(math.floor(a.num("count", lo=1, hi=MAX_ARRAY) + 0.5))
    if kind == "linear":
        return {"type": kind, "count": count, "step": a.vec("step", 3)}
    axis = raw.get("axis", "y")
    if axis not in ("x", "y", "z"):
        raise SpecError(f"{a.at('axis')}: expected 'x', 'y' or 'z'")
    return {"type": kind, "count": count, "axis": axis, "radius": a.num("radius", 0.0),
            "start": math.radians(a.num("start_deg", 0.0))}


def _node(raw: Any, index: int, env: dict[str, float], notes: list[str]) -> Node:
    path = f"parts[{index}]"
    r = Reader(raw, path, env)
    pid = raw.get("id")
    if not isinstance(pid, str) or not pid or len(pid) > 40 or not all(c.isalnum() or c in "_-" for c in pid):
        raise SpecError(f"{path}.id: expected a short name of letters, digits, '_' and '-'")
    kind = raw.get("kind")
    if kind not in KIND_KEYS:
        raise SpecError(f"{path}.kind: unknown kind {kind!r}" + did_you_mean(str(kind), KIND_KEYS))
    check_keys(raw, COMMON_KEYS | KIND_KEYS[kind], path)
    n = Node(pid, kind, path, name=r.text("name", pid), pos=r.vec("pos", 3, [0, 0, 0]),
             rot=[math.radians(x) for x in r.vec("rot", 3, [0, 0, 0])], parent=raw.get("parent"))
    build(kind, n, r, notes)
    n.rot = clean(n.rot)
    if "color" in raw:
        n.color = r.text("color", limit=40)
    tags = raw.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise SpecError(f"{path}.tags: expected a list of text")
    n.tags = list(tags)
    if "material" in raw:
        m = Reader(raw["material"], r.at("material"), env)
        check_keys(m.raw, MATERIAL_KEYS, m.path)
        n.props.update({k: m.num(k, lo=0, hi=1) for k in ("metal", "rough") if m.has(k)})
        n.opacity = m.num("opacity", lo=0, hi=1) if m.has("opacity") else None
    if "mirror" in raw:
        if raw["mirror"] not in ("x", "y", "z"):
            raise SpecError(f"{path}.mirror: expected 'x', 'y' or 'z'")
        n.mirror = raw["mirror"]
    n.array = _array(r)
    return n


def _tree(spec: dict, env: dict[str, float], notes: list[str]) -> list[Node]:
    raw_parts = spec.get("parts")
    if not isinstance(raw_parts, list) or not raw_parts:
        raise SpecError("parts: expected a non-empty list")
    for i, raw in enumerate(raw_parts):
        if not isinstance(raw, dict):
            raise SpecError(f"parts[{i}]: expected an object")
    nodes: dict[str, Node] = {}
    for i, raw in enumerate(raw_parts):
        n = _node(raw, i, env, notes)
        if n.id in nodes:
            raise SpecError(f"parts[{i}].id: duplicate id '{n.id}' (first used at {nodes[n.id].path})")
        nodes[n.id] = n
    roots: list[Node] = []
    for n in nodes.values():
        if n.parent is None:
            roots.append(n)
            continue
        parent = nodes.get(n.parent) if isinstance(n.parent, str) else None
        if parent is None:
            raise SpecError(f"{join(n.path, 'parent')}: unknown part {n.parent!r}" + did_you_mean(str(n.parent), nodes))
        if parent.kind != "group":
            raise SpecError(f"{join(n.path, 'parent')}: '{parent.id}' is a {parent.kind}, only a group can hold parts")
        parent.children.append(n)
    for n in nodes.values():  # depth and cycles: walk up, a part at depth 1 has no parent
        cur, depth = n, 1
        while cur.parent is not None:
            cur, depth = nodes[cur.parent], depth + 1
            if cur is n:
                raise SpecError(f"{join(n.path, 'parent')}: parent chain forms a cycle")
            if depth > MAX_DEPTH:
                raise SpecError(f"{n.path}: groups are nested deeper than {MAX_DEPTH}")
    return roots


def _flatten(n: Node, parent: str | None, out: list[dict[str, Any]]) -> None:
    out.append({"id": n.id, "kind": n.kind, "name": n.name, "parent": parent, "pos": clean(n.pos), "rot": clean(n.rot),
                "scale": [round(x, 6) for x in n.scale] if isinstance(n.scale, list) else n.scale, "color": n.color,
                "opacity": n.opacity, "layer": n.tags[0] if n.tags else "body", "tags": list(n.tags),
                "props": {"source": n.props.get("source", n.id.split(".")[0]), **n.props}, "geom": n.geom})
    for c in n.children:
        _flatten(c, n.id, out)


def expand(spec: dict) -> Expanded:
    if not isinstance(spec, dict):
        raise SpecError("spec: expected an object")
    check_keys(spec, TOP_KEYS, "")
    units = spec.get("units", "mm")
    if units not in UNITS:
        raise SpecError(f"units: expected one of {', '.join(UNITS)}, got {units!r}")
    result = Expanded()
    result.params = read_params(spec.get("params"), result.notes)
    roots = _tree(spec, param_env(result.params), result.notes)
    total = sum(size(n) for n in roots)
    if total > MAX_PARTS:
        raise SpecError(f"parts: the spec expands to {total} parts, the limit is {MAX_PARTS}")
    for root in roots:
        for inst in instances(root):
            _flatten(inst, None, result.parts)
    seen: set[str] = set()
    for p in result.parts:
        if p["id"] in seen:
            raise SpecError(f"parts: expansion produced the id '{p['id']}' twice (an id like 'a.0' clashes with an array of 'a')")
        seen.add(p["id"])
    return result
