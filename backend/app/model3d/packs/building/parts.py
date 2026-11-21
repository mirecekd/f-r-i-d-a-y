# backend/app/model3d/packs/building/parts.py
"""Small constructors for part dicts (metres, y up; plan x, y becomes world x, z)."""

from typing import Any


def box(pid: str, name: str, pos: list[float], size: list[float], layer: str, color: str, parent: str | None,
        rot: list[float] | None = None, opacity: float | None = None, props: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": pid, "kind": "box", "name": name, "parent": parent, "pos": [round(v, 4) for v in pos],
            "rot": rot or [0.0, 0.0, 0.0], "scale": [round(max(v, 0.001), 4) for v in size], "color": color,
            "opacity": opacity, "layer": layer, "props": props or {}}


def group(pid: str, name: str, pos: list[float], layer: str, parent: str | None, rot: list[float] | None = None,
          props: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": pid, "kind": "group", "name": name, "parent": parent, "pos": [round(v, 4) for v in pos],
            "rot": rot or [0.0, 0.0, 0.0], "layer": layer, "props": props or {}}


def text(pid: str, label: str, pos: list[float], layer: str, parent: str | None, size: float = 0.35) -> dict[str, Any]:
    return {"id": pid, "kind": "text", "name": label, "parent": parent, "pos": [round(v, 4) for v in pos],
            "layer": layer, "color": "#ffffff", "geom": {"text": label, "size": size}, "props": {}}
