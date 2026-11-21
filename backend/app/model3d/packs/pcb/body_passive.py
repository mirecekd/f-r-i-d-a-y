# backend/app/model3d/packs/pcb/body_passive.py
"""Chip resistors, capacitors and LEDs (0402 / 0603 / 0805)."""

from typing import Any

from app.model3d.packs.pcb.body_base import BLACK, LED_COLORS, SILVER, TAN, Body, Pad

# size: (body length, body width, body height, pad centre offset, pad length, pad width)
CHIPS = {"0402": (1.0, 0.5, 0.35, 0.5, 0.55, 0.6), "0603": (1.6, 0.8, 0.45, 0.8, 0.8, 0.95), "0805": (2.0, 1.25, 0.6, 1.0, 1.0, 1.45)}


def chip_size(c: dict[str, Any]) -> str:
    fp = str(c.get("footprint") or "")
    return next((s for s in CHIPS if s in fp), "0603")


def _chip(c: dict[str, Any], pid: str, body_color: str, cap: bool = True) -> Body:
    length, width, h, off, pl, pw = CHIPS[chip_size(c)]
    b = Body(pid, half=(off + pl / 2 + 0.2, pw / 2 + 0.2))
    b.box("body", 0, 0, 0.02, length - 0.5 * length * 0.4, width * 0.95, h * 0.95, body_color)
    if cap:
        end = length * 0.22
        for i, s in enumerate((-1, 1)):
            b.box(f"cap{i + 1}", s * (length - end) / 2, 0, 0, end, width, h, SILVER)
    b.pads = [Pad("1", -off, 0, pl, pw), Pad("2", off, 0, pl, pw)]
    return b


def resistor(c: dict[str, Any], pid: str) -> Body:
    return _chip(c, pid, BLACK)


def capacitor(c: dict[str, Any], pid: str) -> Body:
    return _chip(c, pid, TAN)


def led(c: dict[str, Any], pid: str) -> Body:
    length, width, h, off, pl, pw = CHIPS[chip_size(c)]
    b = Body(pid, half=(off + pl / 2 + 0.2, pw / 2 + 0.2))
    color = LED_COLORS.get(str(c.get("value") or "red").lower(), LED_COLORS["red"])
    b.box("base", 0, 0, 0, length, width, h * 0.45, "#e8e4d8")
    b.box("lens", 0, 0, h * 0.45, length * 0.85, width * 0.9, h * 0.75, color)
    b.box("cathode", -length * 0.36, 0, h * 1.2, length * 0.1, width * 0.9, 0.03, BLACK)
    b.pads = [Pad("1", -off, 0, pl, pw), Pad("2", off, 0, pl, pw)]
    return b
