# backend/app/workshop/reader.py
"""Typed access to spec objects (every error names the field path) and the evaluated Node of one part."""

from dataclasses import dataclass, field
from typing import Any

from app.workshop.expr import SpecError, did_you_mean, number


def join(path: str, key: str | int) -> str:
    if isinstance(key, int):
        return f"{path}[{key}]"
    return f"{path}.{key}" if path else key


def check_keys(raw: dict, allowed: set[str], path: str) -> None:
    for k in raw:
        if k not in allowed:
            raise SpecError(f"{join(path, str(k))}: unknown key" + did_you_mean(str(k), allowed))


class Reader:
    """Typed access to one spec object; every error names the field path."""

    def __init__(self, raw: Any, path: str, env: dict[str, float]):
        if not isinstance(raw, dict):
            raise SpecError(f"{path}: expected an object")
        self.raw, self.path, self.env = raw, path, env

    def at(self, key: str | int) -> str:
        return join(self.path, key)

    def has(self, key: str) -> bool:
        return key in self.raw

    def num(self, key: str, default: float | None = None, *, lo: float | None = None, hi: float | None = None,
            positive: bool = False) -> float:
        if key not in self.raw:
            if default is None:
                raise SpecError(f"{self.at(key)}: required")
            return default
        v = number(self.raw[key], self.env, self.at(key))
        if (positive and v <= 0) or (lo is not None and v < lo) or (hi is not None and v > hi):
            want = "> 0" if positive else f"between {lo} and {hi}" if lo is not None and hi is not None else f">= {lo}" if lo is not None else f"<= {hi}"
            raise SpecError(f"{self.at(key)}: must be {want}, got {v:g}")
        return v

    def vec(self, key: str, n: int, default: list[float] | None = None, *, positive: bool = False) -> list[float]:
        if key not in self.raw:
            if default is None:
                raise SpecError(f"{self.at(key)}: required")
            return list(default)
        return self.numbers(self.raw[key], self.at(key), n, positive)

    def numbers(self, raw: Any, path: str, n: int, positive: bool = False) -> list[float]:
        if not isinstance(raw, list) or len(raw) != n:
            raise SpecError(f"{path}: expected a list of {n} numbers")
        out = [number(x, self.env, f"{path}[{i}]") for i, x in enumerate(raw)]
        for i, v in enumerate(out):
            if positive and v <= 0:
                raise SpecError(f"{path}[{i}]: must be > 0, got {v:g}")
        return out

    def points(self, key: str, dim: int, lo: int, hi: int) -> list[list[float]]:
        raw = self.raw.get(key)
        if not isinstance(raw, list) or not lo <= len(raw) <= hi:
            raise SpecError(f"{self.at(key)}: expected a list of {lo}..{hi} points of {dim} numbers")
        return [self.numbers(p, f"{self.at(key)}[{i}]", dim) for i, p in enumerate(raw)]

    def text(self, key: str, default: str | None = None, limit: int = 200) -> str:
        v = self.raw.get(key, default)
        if not isinstance(v, str) or (not v and default is None) or len(v) > limit:
            raise SpecError(f"{self.at(key)}: expected a text of 1..{limit} characters")
        return v

    def flag(self, key: str, default: bool = False) -> bool:
        v = self.raw.get(key, default)
        if not isinstance(v, bool):
            raise SpecError(f"{self.at(key)}: expected true or false")
        return v


@dataclass
class Node:
    """One evaluated part of the tree, before mirror/array instancing. Angles in radians, sizes in spec units."""

    id: str
    kind: str
    path: str
    geom: dict[str, Any] = field(default_factory=dict)
    scale: Any = 1.0
    name: str = ""
    parent: str | None = None
    pos: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    rot: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    color: str | None = None
    opacity: float | None = None
    tags: list[str] = field(default_factory=list)
    props: dict[str, Any] = field(default_factory=dict)
    mirror: str | None = None
    array: dict[str, Any] | None = None
    children: list["Node"] = field(default_factory=list)


