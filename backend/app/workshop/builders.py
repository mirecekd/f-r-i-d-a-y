# backend/app/workshop/builders.py
"""Part kinds of the spec: each builder turns one validated spec object into a Node (scene kind, geom, scale, children)."""

import math

from app.workshop.expr import SpecError
from app.workshop.reader import Node, Reader
from app.workshop.xform import local_rotate

KIND_KEYS: dict[str, set[str]] = {
    "box": {"size"}, "sphere": {"r"}, "cylinder": {"r", "r1", "r2", "h"}, "capsule": {"r", "h"}, "torus": {"r", "tube"},
    "plane": {"size"}, "extrude": {"outline", "h"}, "lathe": {"profile", "segments"}, "polyline": {"pts", "width", "closed"}, "label": {"text", "size"},
    "group": set(),
}
TORUS_TUBE_RATIO = 0.3  # the scene torus has a fixed tube radius of 0.3 x the ring radius


def _cylinder(n: Node, r: Reader, notes: list[str]) -> None:
    h = r.num("h", positive=True)
    if r.has("r") == (r.has("r1") or r.has("r2")):
        raise SpecError(f"{r.path}: give either 'r' or both 'r1' and 'r2'")
    r1 = r.num("r", positive=True) if r.has("r") else r.num("r1", lo=0)
    r2 = r1 if r.has("r") else r.num("r2", lo=0)
    if r1 == 0 and r2 == 0:
        raise SpecError(f"{r.path}: r1 and r2 cannot both be 0")
    if r1 == r2:
        n.kind, n.scale = "cylinder", [2 * r1, h, 2 * r1]
    elif r2 == 0 or r1 == 0:  # the scene cone has its apex up; a cone with the apex down is turned over
        n.kind, n.scale = "cone", [2 * max(r1, r2)] * 3
        n.scale[1] = h
        if r1 == 0:
            n.rot = local_rotate(n.rot, "x", math.pi)
    else:
        mean = (r1 + r2) / 2
        n.kind, n.scale = "cylinder", [2 * mean, h, 2 * mean]
        notes.append(f"{r.path}: frustum r1={r1:g} r2={r2:g} is approximated by a cylinder of mean radius {mean:g}")


def _capsule(n: Node, r: Reader) -> None:
    rad, total = r.num("r", positive=True), r.num("h", positive=True)
    if total < 2 * rad:
        raise SpecError(f"{r.at('h')}: capsule height {total:g} must be at least 2*r = {2 * rad:g}")
    body = total - 2 * rad
    n.kind = "group"

    def child(suffix: str, kind: str, scale: list[float], y: float) -> Node:
        return Node(f"{n.id}.{suffix}", kind, n.path, scale=scale, pos=[0.0, y, 0.0], props={"source": n.id})

    if body > 0:
        n.children.append(child("body", "cylinder", [2 * rad, body, 2 * rad], 0.0))
    n.children.append(child("top", "sphere", [2 * rad] * 3, body / 2))
    n.children.append(child("bottom", "sphere", [2 * rad] * 3, -body / 2))


def _torus(n: Node, r: Reader, notes: list[str]) -> None:
    ring, tube = r.num("r", positive=True), r.num("tube", positive=True)
    n.scale = [2 * ring, 2 * ring, tube / 0.15]  # ring in the xy plane, then laid flat (axis y)
    n.rot = local_rotate(n.rot, "x", math.pi / 2)
    if abs(tube - TORUS_TUBE_RATIO * ring) > 0.15 * TORUS_TUBE_RATIO * ring:
        notes.append(f"{r.path}: torus tube {tube:g} differs from {TORUS_TUBE_RATIO:g}*r; its cross-section is slightly oval")


def _lathe(n: Node, r: Reader) -> None:
    profile = r.points("profile", 2, 2, 64)
    for i, (radius, _y) in enumerate(profile):
        if radius < 0:
            raise SpecError(f"{r.at('profile')}[{i}][0]: radius must be >= 0, got {radius:g}")
    segments = int(r.num("segments", 24, lo=3, hi=96) + 0.5)
    n.geom = {"profile": profile, "segments": segments}


def build(kind: str, n: Node, r: Reader, notes: list[str]) -> None:
    """Fill the kind specific part of `n` (scene kind, geom, scale, local rotation, children)."""
    n.kind = kind
    if kind == "box":
        n.scale = r.vec("size", 3, positive=True)
    elif kind == "sphere":
        n.scale = [2 * r.num("r", positive=True)] * 3
    elif kind == "cylinder":
        _cylinder(n, r, notes)
    elif kind == "capsule":
        _capsule(n, r)
    elif kind == "torus":
        _torus(n, r, notes)
    elif kind == "plane":
        sx, sz = r.vec("size", 2, positive=True)
        n.scale = [sx, sz, 1.0]
        n.rot = local_rotate(n.rot, "x", -math.pi / 2)
    elif kind == "extrude":
        n.geom = {"outline": r.points("outline", 2, 3, 64), "height": r.num("h", positive=True), "floor": False}
    elif kind == "lathe":
        _lathe(n, r)
    elif kind == "polyline":
        n.geom = {"pts": r.points("pts", 3, 2, 256), "closed": r.flag("closed")}
        if r.has("width"):
            n.props["width"] = r.num("width", positive=True)
    elif kind == "label":
        n.geom = {"text": r.text("text")}
        if r.has("size"):
            n.geom["size"] = r.num("size", positive=True)
