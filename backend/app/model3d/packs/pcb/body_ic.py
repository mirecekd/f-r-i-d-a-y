# backend/app/model3d/packs/pcb/body_ic.py
"""SOIC-8/14/16 with gull-wing leads and QFP-32/44/64 with flat leads."""

from typing import Any

from app.model3d.packs.pcb.body_base import BLACK, SILVER, Body, Pad

SOIC_LEN = {8: 4.9, 14: 8.65, 16: 9.9}
# pins: (body size, pitch, leads per side)
QFP = {32: (7.0, 0.8, 8), 44: (10.0, 0.8, 11), 64: (10.0, 0.5, 16)}
MARK = "#6a6a72"


def _count(c: dict[str, Any], table: dict[int, Any], default: int, what: str) -> int:
    n = c.get("pins") or default
    if n not in table:
        raise ValueError(f"{what}: pins must be one of {sorted(table)}")
    return int(n)


def soic(c: dict[str, Any], pid: str) -> Body:
    n = _count(c, SOIC_LEN, 8, f"soic {pid}")
    length, width, pitch, row = SOIC_LEN[n], 3.9, 1.27, 5.4
    b = Body(pid, half=(row / 2 + 1.2, length / 2 + 0.3))
    b.box("body", 0, 0, 0.1, width, length, 1.5, BLACK)
    b.cyl("pin1", -width / 2 + 0.7, length / 2 - 0.7, 1.6, 0.7, 0.02, MARK)
    per = n // 2
    for i in range(n):
        left = i < per
        y = ((per - 1) / 2 - i) * pitch if left else (i - per - (per - 1) / 2) * pitch
        s = -1 if left else 1
        b.pads.append(Pad(str(i + 1), s * row / 2, y, 1.5, 0.6))
        b.box(f"l{i + 1}_up", s * (width / 2 + 0.2), y, 0.45, 0.5, 0.4, 0.25, SILVER)
        b.box(f"l{i + 1}_ft", s * (width / 2 + 0.55), y, 0.0, 1.3, 0.4, 0.2, SILVER)
    return b


def qfp(c: dict[str, Any], pid: str) -> Body:
    n = _count(c, QFP, 32, f"qfp {pid}")
    body, pitch, per = QFP[n]
    pad_c = body / 2 + 0.9
    b = Body(pid, half=(pad_c + 0.9, pad_c + 0.9))
    b.box("body", 0, 0, 0.1, body, body, 1.3, BLACK)
    b.cyl("pin1", -body / 2 + 0.9, body / 2 - 0.9, 1.4, 0.8, 0.02, MARK)
    for i in range(n):
        side, k = divmod(i, per)
        t = (k - (per - 1) / 2) * pitch
        # side 0 left (top to bottom), 1 bottom (left to right), 2 right (bottom to top), 3 top (right to left)
        px, py, horizontal = [(-pad_c, -t, True), (t, -pad_c, False), (pad_c, t, True), (-t, pad_c, False)][side]
        sx, sy = (1.6, pitch * 0.55) if horizontal else (pitch * 0.55, 1.6)
        b.pads.append(Pad(str(i + 1), px, py, sx, sy))
        reach = 1.1
        if horizontal:
            b.box(f"l{i + 1}", (1 if px > 0 else -1) * (body / 2 + reach / 2 - 0.1), py, 0.0, reach, pitch * 0.35, 0.2, SILVER)
        else:
            b.box(f"l{i + 1}", px, (1 if py > 0 else -1) * (body / 2 + reach / 2 - 0.1), 0.0, pitch * 0.35, reach, 0.2, SILVER)
    return b
