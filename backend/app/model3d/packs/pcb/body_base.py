# backend/app/model3d/packs/pcb/body_base.py
"""Shared types for the component body library. Body coordinates are local mm: x right, y plan-up, z above the board."""

from dataclasses import dataclass, field
from typing import Any

from app.model3d.packs.pcb.layers import box, cyl

BLACK = "#1c1c20"
SILVER = "#b9bec6"
TAN = "#b08850"
GOLD = "#e0c070"
LED_COLORS = {"red": "#ff3b30", "green": "#34d058", "blue": "#3b82ff", "yellow": "#ffd60a", "white": "#f4f4f4", "orange": "#ff9500"}


@dataclass
class Pad:
    pin: str
    x: float
    y: float
    sx: float
    sy: float


@dataclass
class Body:
    """Parts are children of the component group `pid`; pads become copper parts; half = outline half size (x, y)."""
    pid: str
    parts: list[dict[str, Any]] = field(default_factory=list)
    pads: list[Pad] = field(default_factory=list)
    half: tuple[float, float] = (1.0, 1.0)

    def box(self, name: str, cx: float, cy: float, z0: float, sx: float, sy: float, h: float, color: str) -> None:
        self.parts.append(box(f"{self.pid}_{name}", "components", cx, cy, z0, sx, sy, h, color=color, parent=self.pid,
                              opacity=1.0, name=name))

    def cyl(self, name: str, cx: float, cy: float, z0: float, d: float, h: float, color: str) -> None:
        self.parts.append(cyl(f"{self.pid}_{name}", "components", cx, cy, z0, d, h, color=color, parent=self.pid,
                              opacity=1.0, name=name))
