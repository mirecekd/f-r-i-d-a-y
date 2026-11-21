# backend/app/model3d/packs/pcb/library.py
"""Component body library: kind -> procedural body builder (standard package dimensions, own code)."""

from collections.abc import Callable
from typing import Any

from app.model3d.packs.pcb.body_base import Body
from app.model3d.packs.pcb.body_conn import (
    crystal,
    esp32_module,
    generic,
    pin_header,
    usb_c,
)
from app.model3d.packs.pcb.body_ic import qfp, soic
from app.model3d.packs.pcb.body_passive import capacitor, led, resistor

BUILDERS: dict[str, Callable[[dict[str, Any], str], Body]] = {
    "resistor": resistor, "capacitor": capacitor, "led": led, "soic": soic, "qfp": qfp, "pin_header": pin_header,
    "usb_c": usb_c, "crystal": crystal, "esp32_module": esp32_module, "generic": generic,
}


def build_body(comp: dict[str, Any], pid: str) -> Body:
    return BUILDERS[comp["kind"]](comp, pid)
