# backend/app/model3d/packs/building/geom.py
"""Plan geometry helpers in metres (plan x, y; y runs down the page and maps to world z)."""

import itertools
import math

TOL = 1e-4
Point = list[float]


def bbox(poly: list[Point]) -> tuple[float, float, float, float]:
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def rect_poly(x: float, y: float, w: float, d: float) -> list[Point]:
    """Rectangle corners in edge order: n (top), e (right), s (bottom), w (left)."""
    return [[x, y], [x + w, y], [x + w, y + d], [x, y + d]]


def area(poly: list[Point]) -> float:
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in edges(poly))) / 2


def edges(poly: list[Point]) -> list[tuple[Point, Point]]:
    return list(zip(poly, poly[1:] + poly[:1], strict=True))


def seg_param(p: Point, a: Point, b: Point) -> tuple[float, float]:
    """(t, distance): p projected on line a-b, t is unclamped and 0..1 along a->b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = dx * dx + dy * dy
    if n == 0:
        return 0.0, math.dist(p, a)
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / n
    return t, math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def split_points(a: Point, b: Point, others: list[Point]) -> list[Point]:
    """`a`, every point of `others` strictly inside segment a-b (sorted along it), then `b`."""
    ts = {0.0, 1.0}
    for p in others:
        t, dist = seg_param(p, a, b)
        if dist <= TOL < t * math.dist(a, b) < math.dist(a, b) - TOL:
            ts.add(round(t, 6))
    return [[a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t] for t in sorted(ts)]


def unique_segments(polys: list[list[Point]]) -> list[tuple[Point, Point]]:
    """Room edges split at T-junctions and deduplicated, so an edge shared by two rooms yields one segment."""
    corners = [p for poly in polys for p in poly]
    seen: dict[tuple[float, ...], tuple[Point, Point]] = {}
    for poly in polys:
        for a, b in edges(poly):
            pts = split_points(a, b, corners)
            for p, q in itertools.pairwise(pts):
                key = tuple(sorted([(round(p[0], 3), round(p[1], 3)), (round(q[0], 3), round(q[1], 3))]))
                seen.setdefault(tuple(c for pt in key for c in pt), (p, q))
    return list(seen.values())
