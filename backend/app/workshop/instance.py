# backend/app/workshop/instance.py
"""Mirror and array instancing of Node subtrees with stable concrete ids (<id>, <id>.m, <id>.<i>, <id>.<i>.m)."""

import copy
import dataclasses
import math

from app.workshop.expr import SpecError
from app.workshop.reader import Node
from app.workshop.xform import AXES, apply, axis_matrix, compose_euler, mirror_euler, mirror_pos

MAX_PARTS = 2000
RADIAL_OFFSET = {"x": 1, "y": 0, "z": 0}  # the radius moves the member along y (axis x) or x (axes y and z)


def _rename(n: Node, suffix: str) -> None:
    n.id += suffix
    for c in n.children:
        _rename(c, suffix)


def _mirror_geom(n: Node, axis: str) -> None:
    k = AXES[axis]
    if n.kind == "polyline":
        n.geom["pts"] = [[-v if i == k else v for i, v in enumerate(p)] for p in n.geom["pts"]]
    elif n.kind == "lathe" and k == 1:  # x and z mirrors leave a surface of revolution unchanged
        n.geom["profile"] = [[radius, -y] for radius, y in n.geom["profile"]]
    elif n.kind == "extrude":
        if k == 1:
            raise SpecError(f"{n.path}: mirror 'y' of an extrude is not supported (it would extrude downwards)")
        n.geom["outline"] = [[-v if i == k // 2 else v for i, v in enumerate(p)] for p in n.geom["outline"]]


def _mirror(n: Node, axis: str) -> None:
    n.pos, n.rot = mirror_pos(n.pos, axis), mirror_euler(n.rot, axis)
    _mirror_geom(n, axis)
    for c in n.children:
        _mirror(c, axis)


def _member(n: Node, arr: dict, i: int) -> Node:
    m = copy.deepcopy(n)
    _rename(m, f".{i}")
    if arr["type"] == "linear":
        m.pos = [p + s * i for p, s in zip(m.pos, arr["step"], strict=True)]
        return m
    base = list(m.pos)
    base[RADIAL_OFFSET[arr["axis"]]] += arr["radius"]
    rot = axis_matrix(arr["axis"], arr["start"] + 2 * math.pi * i / arr["count"])
    m.pos, m.rot = apply(rot, base), compose_euler(rot, m.rot)
    return m


def size(n: Node) -> int:
    """Number of parts the node produces once mirror/array are expanded."""
    members = n.array["count"] if n.array else 1
    return (1 + sum(size(c) for c in n.children)) * members * (2 if n.mirror else 1)


def instances(n: Node) -> list[Node]:
    base = dataclasses.replace(n, children=[i for c in n.children for i in instances(c)])
    members = [_member(base, n.array, i) for i in range(n.array["count"])] if n.array else [base]
    if not n.mirror:
        return members
    mirrored = []
    for m in members:
        c = copy.deepcopy(m)
        _rename(c, ".m")
        _mirror(c, n.mirror)
        mirrored.append(c)
    return members + mirrored
