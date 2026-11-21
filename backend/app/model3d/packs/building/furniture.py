# backend/app/model3d/packs/building/furniture.py
"""Furniture as box assemblies. Local frame: x width, z depth (front is +z), y up from the floor, metres."""

from typing import Any

# kind -> (default [width, depth, height], colour)
DEFAULTS: dict[str, tuple[list[float], str]] = {
    "bed": ([1.6, 2.0, 0.55], "#e0a96d"),
    "sofa": ([2.0, 0.9, 0.85], "#7f9fd9"),
    "table": ([1.4, 0.8, 0.75], "#c99a62"),
    "desk": ([1.4, 0.7, 0.75], "#c99a62"),
    "chair": ([0.45, 0.45, 0.9], "#d98f6f"),
    "wardrobe": ([1.0, 0.6, 2.0], "#b88a5e"),
    "kitchen_unit": ([2.4, 0.6, 0.9], "#cfc7b8"),
    "generic": ([0.8, 0.8, 0.8], "#b0b8c4"),
}


def default_size(kind: str) -> list[float]:
    return list(DEFAULTS[kind][0])


def default_color(kind: str) -> str:
    return DEFAULTS[kind][1]


def pieces(kind: str, size: list[float], color: str) -> list[dict[str, Any]]:
    """Boxes as {name, pos, size, color}; pos is the box centre in the item's local frame."""
    w, d, h = size
    if kind in ("table", "desk"):
        top, leg = 0.05, 0.06
        out = [{"name": "top", "pos": [0, h - top / 2, 0], "size": [w, top, d], "color": color}]
        for i, (sx, sz) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)]):
            out.append({"name": f"leg{i}", "pos": [sx * (w / 2 - leg), (h - top) / 2, sz * (d / 2 - leg)],
                        "size": [leg, h - top, leg], "color": "#8a6a45"})
        return out
    if kind == "bed":
        base = h * 0.6
        return [{"name": "base", "pos": [0, base / 2, 0], "size": [w, base, d], "color": color},
                {"name": "mattress", "pos": [0, base + 0.08, 0.04], "size": [w - 0.08, 0.16, d - 0.14], "color": "#e9e4d8"},
                {"name": "headboard", "pos": [0, h * 0.95, -d / 2 + 0.04], "size": [w, h * 1.1, 0.08], "color": "#9c6f43"},
                {"name": "pillow", "pos": [0, base + 0.2, -d / 2 + 0.3], "size": [w * 0.7, 0.1, 0.35], "color": "#ffffff"}]
    if kind == "sofa":
        return [{"name": "seat", "pos": [0, h * 0.25, 0.1], "size": [w, h * 0.5, d - 0.2], "color": color},
                {"name": "back", "pos": [0, h / 2, -d / 2 + 0.1], "size": [w, h, 0.2], "color": color},
                {"name": "arm_l", "pos": [-w / 2 + 0.1, h * 0.35, 0.1], "size": [0.2, h * 0.7, d - 0.2], "color": "#6a88c4"},
                {"name": "arm_r", "pos": [w / 2 - 0.1, h * 0.35, 0.1], "size": [0.2, h * 0.7, d - 0.2], "color": "#6a88c4"}]
    if kind == "chair":
        return [{"name": "seat", "pos": [0, h * 0.5, 0], "size": [w, 0.05, d], "color": color},
                {"name": "back", "pos": [0, h * 0.75, -d / 2 + 0.025], "size": [w, h * 0.5, 0.05], "color": color},
                {"name": "legs", "pos": [0, h * 0.25, 0], "size": [w * 0.8, h * 0.5, d * 0.8], "color": "#8a6a45"}]
    if kind == "wardrobe":
        return [{"name": "body", "pos": [0, h / 2, 0], "size": [w, h, d], "color": color},
                {"name": "doors", "pos": [0, h / 2, d / 2 + 0.005], "size": [w * 0.96, h * 0.94, 0.01], "color": "#a07850"}]
    if kind == "kitchen_unit":
        return [{"name": "base", "pos": [0, (h - 0.04) / 2, 0], "size": [w, h - 0.04, d], "color": color},
                {"name": "worktop", "pos": [0, h - 0.02, 0.02], "size": [w + 0.02, 0.04, d + 0.04], "color": "#5b5f66"}]
    return [{"name": "body", "pos": [0, h / 2, 0], "size": [w, h, d], "color": color}]
