# backend/app/entities/layout.py
"""Deterministic auto-layout for entity tiles: pure functions, no scene or network access."""

import math

SPACING = 3.5  # minimum distance between two entity centres
ARC_RADIUS = 6.0
ARC_SPAN = math.radians(160)
FRONT_Z = 2.0  # the camera looks from +z, so the arc opens towards it
BASE_Y = 1.2
MAX_RINGS = 40

Pos = list[float]


def _far_enough(p: Pos, taken: list[Pos], spacing: float) -> bool:
    return all(math.hypot(p[0] - q[0], p[2] - q[2]) >= spacing - 1e-6 for q in taken)


def arc_slots(ring: int) -> list[Pos]:
    """Slots of one ring of the arc in front of the camera area, left to right."""
    radius = ARC_RADIUS + ring * SPACING
    count = max(1, int(ARC_SPAN * radius // SPACING) + 1)
    if count == 1:
        return [[0.0, BASE_Y, FRONT_Z - radius]]
    out: list[Pos] = []
    for i in range(count):
        a = -ARC_SPAN / 2 + ARC_SPAN * i / (count - 1)
        out.append([round(radius * math.sin(a), 3), BASE_Y, round(FRONT_Z - radius * math.cos(a), 3)])
    return out


def next_free_slot(taken: list[Pos], spacing: float = SPACING) -> Pos:
    """The first arc slot that keeps `spacing` from every taken position (x/z plane)."""
    for ring in range(MAX_RINGS):
        for slot in arc_slots(ring):
            if _far_enough(slot, taken, spacing):
                return slot
    return [0.0, BASE_Y, FRONT_Z - ARC_RADIUS - MAX_RINGS * SPACING]


def arrange(count: int, layout: str, center: Pos | None = None) -> list[Pos]:
    """`count` positions for a re-layout: 'arc' (rings), 'grid' (rows facing the camera) or 'around' (circle about `center`)."""
    c = center or [0.0, BASE_Y, 0.0]
    if layout == "grid":
        cols = max(1, math.ceil(math.sqrt(count)))
        rows = math.ceil(count / cols)
        return [
            [round((i % cols - (cols - 1) / 2) * SPACING, 3), BASE_Y, round(FRONT_Z - 4 - (rows - 1 - i // cols) * SPACING, 3)]
            for i in range(count)
        ]
    if layout == "around":
        radius = max(SPACING, SPACING / (2 * math.sin(math.pi / count))) if count > 1 else SPACING
        return [
            [round(c[0] + radius * math.cos(2 * math.pi * i / max(count, 1)), 3), c[1],
             round(c[2] + radius * math.sin(2 * math.pi * i / max(count, 1)), 3)]
            for i in range(count)
        ]
    out: list[Pos] = []
    for ring in range(MAX_RINGS):
        out.extend(arc_slots(ring))
        if len(out) >= count:
            break
    return out[:count]
