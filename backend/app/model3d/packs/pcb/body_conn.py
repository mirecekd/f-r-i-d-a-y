# backend/app/model3d/packs/pcb/body_conn.py
"""Pin headers, USB-C receptacle, crystals, ESP32 module and a generic block."""

from typing import Any

from app.model3d.packs.pcb.body_base import BLACK, GOLD, SILVER, Body, Pad

PITCH = 2.54
ESP_COLOR = "#2d3340"


def pin_header(c: dict[str, Any], pid: str) -> Body:
    n = int(c.get("pins") or 4)
    rows = 2 if "2x" in str(c.get("footprint") or "") else 1
    per = -(-n // rows)
    b = Body(pid, half=(rows * PITCH / 2 + 0.3, per * PITCH / 2 + 0.3))
    b.box("housing", 0, 0, 0, rows * PITCH, per * PITCH, 2.5, BLACK)
    for i in range(n):
        r, k = divmod(i, per)
        x = (r - (rows - 1) / 2) * PITCH
        y = ((per - 1) / 2 - k) * PITCH
        b.pads.append(Pad(str(i + 1), x, y, 1.7, 1.7))
        b.box(f"pin{i + 1}", x, y, 2.5, 0.64, 0.64, 6.0, GOLD)
    return b


def usb_c(c: dict[str, Any], pid: str) -> Body:
    w, d, h = 8.94, 7.3, 3.26
    b = Body(pid, half=(w / 2 + 0.5, d / 2 + 0.5))
    b.box("shell", 0, -0.5, 0, w, d, h, SILVER)
    b.box("opening", 0, -d / 2 - 0.02, 0.5, 7.4, 0.12, h - 1.0, BLACK)
    b.box("tongue", 0, -d / 2 + 0.3, 1.05, 6.4, 0.2, 0.6, "#3a3a40")
    for i, x in enumerate((-3.2, -1.0, 1.0, 3.2)):
        b.pads.append(Pad(str(i + 1), x * 0.8, d / 2 - 1.5, 0.6, 1.6))
    for i, x in enumerate((-4.3, 4.3)):
        b.pads.append(Pad(f"S{i + 1}", x, -1.0, 1.0, 2.0))
    return b


def crystal(c: dict[str, Any], pid: str) -> Body:
    if "3225" in str(c.get("footprint") or "3225") and "HC49" not in str(c.get("footprint") or ""):
        b = Body(pid, half=(2.2, 1.6))
        b.box("body", 0, 0, 0, 3.2, 2.5, 0.8, SILVER)
        b.box("lid", 0, 0, 0.8, 2.6, 1.9, 0.1, "#8a9099")
        b.pads = [Pad("1", -1.1, 0, 1.4, 1.9), Pad("2", 1.1, 0, 1.4, 1.9)]
        return b
    b = Body(pid, half=(6.5, 2.8))
    b.box("body", 0, 0, 0.5, 11.0, 4.7, 3.5, SILVER)
    b.cyl("end1", -5.5, 0, 0.5, 4.7, 3.5, SILVER)
    b.cyl("end2", 5.5, 0, 0.5, 4.7, 3.5, SILVER)
    b.pads = [Pad("1", -2.45, 0, 1.4, 1.4), Pad("2", 2.45, 0, 1.4, 1.4)]
    return b


def esp32_module(c: dict[str, Any], pid: str) -> Body:
    w, d, h, ant = 18.0, 25.5, 3.1, 6.0
    b = Body(pid, half=(w / 2 + 0.3, d / 2 + 0.3))
    b.box("board", 0, 0, 0, w, d, 0.8, "#1a1d24")
    b.box("shield", 0, -(ant / 2), 0.8, 15.5, d - ant - 1.5, h - 0.8, SILVER)
    b.box("antenna", 0, d / 2 - ant / 2, 0.8, 15.0, ant - 0.8, 0.05, GOLD)
    n = 14
    for i in range(n):
        y = (n - 1) / 2 * 1.27 - i * 1.27 - ant / 2 - 1.0
        for s, side in ((-1, "l"), (1, "r")):
            b.pads.append(Pad(f"{side}{i + 1}", s * (w / 2 - 0.4), y, 1.2, 0.9))
    return b


def generic(c: dict[str, Any], pid: str) -> Body:
    pins = int(c.get("pins") or 2)
    w = max(3.0, pins * 0.8)
    b = Body(pid, half=(w / 2 + 1.0, 1.8))
    b.box("body", 0, 0, 0, w, 2.4, 1.2, ESP_COLOR)
    for i in range(pins):
        b.pads.append(Pad(str(i + 1), (i - (pins - 1) / 2) * 1.27 * 1.0, 0, 0.8, 1.6) if pins > 1 else Pad("1", 0, 0, 1.0, 1.0))
    return b
