# backend/app/workshop/xform.py
"""Rotation helpers in the three.js Euler XYZ convention (matrix = Rx * Ry * Rz), angles in radians."""

import math

Mat = list[list[float]]
AXES = {"x": 0, "y": 1, "z": 2}


def _mul(a: Mat, b: Mat) -> Mat:
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def axis_matrix(axis: str, ang: float) -> Mat:
    c, s = math.cos(ang), math.sin(ang)
    if axis == "x":
        return [[1, 0, 0], [0, c, -s], [0, s, c]]
    if axis == "y":
        return [[c, 0, s], [0, 1, 0], [-s, 0, c]]
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def euler_matrix(e: list[float]) -> Mat:
    return _mul(_mul(axis_matrix("x", e[0]), axis_matrix("y", e[1])), axis_matrix("z", e[2]))


def matrix_euler(m: Mat) -> list[float]:
    y = math.asin(max(-1.0, min(1.0, m[0][2])))
    if abs(m[0][2]) < 0.9999999:
        x, z = math.atan2(-m[1][2], m[2][2]), math.atan2(-m[0][1], m[0][0])
    else:
        x, z = math.atan2(m[2][1], m[1][1]), 0.0
    return [x, y, z]


def clean(v: list[float]) -> list[float]:
    return [round(x, 6) + 0.0 for x in v]


def apply(m: Mat, v: list[float]) -> list[float]:
    return [sum(m[i][k] * v[k] for k in range(3)) for i in range(3)]


def mirror_pos(p: list[float], axis: str) -> list[float]:
    out = list(p)
    out[AXES[axis]] = -out[AXES[axis]]
    return out


def mirror_euler(e: list[float], axis: str) -> list[float]:
    """Rotation of the mirrored object: M R M for the reflection M across the plane normal to `axis`."""
    k = AXES[axis]
    m = euler_matrix(e)
    flip = [-1.0 if i == k else 1.0 for i in range(3)]
    return matrix_euler([[flip[i] * flip[j] * m[i][j] for j in range(3)] for i in range(3)])


def compose_euler(outer: Mat, inner: list[float]) -> list[float]:
    return matrix_euler(_mul(outer, euler_matrix(inner)))


def local_rotate(rot: list[float], axis: str, ang: float) -> list[float]:
    """Euler angles of the object rotated by `ang` about its OWN `axis` (applied before its existing rotation)."""
    return matrix_euler(_mul(euler_matrix(rot), axis_matrix(axis, ang)))
