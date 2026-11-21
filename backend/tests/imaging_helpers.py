# backend/tests/imaging_helpers.py
"""Shared fakes for the imaging tests: a context that records emits, stored images and a model session."""

from typing import Any

from app.scene import SceneStore
from app.tools_friday.ctx import Ctx
from app.vision.upload import ingest
from tests.vision_helpers import png_bytes


class FakeCtx(Ctx):
    """A Ctx whose emit records every message in `msgs`."""

    def __init__(self) -> None:
        self.msgs: list[dict[str, Any]] = []

        async def record(msg: dict[str, Any]) -> None:
            self.msgs.append(msg)

        super().__init__(SceneStore(), record)


async def stored_image(color: str = "#3366cc") -> dict[str, Any]:
    return await ingest(png_bytes((320, 200), color), "p.png", "image/png")


def analysis(rooms: list[dict[str, Any]] | None = None, **ext: Any) -> dict[str, Any]:
    """A normalised house analysis (what parse_house returns) for spec_merge tests."""
    room = {"name": "Living", "width_m": 5.0, "depth_m": 4.0, "dimension_source": "label", "dimension_confidence": 0.9,
            "candidates": [], "relative_to": None, "side": None, "floor_material": None, "floor_color": None,
            "doors": [], "windows": [], "furniture": []}
    exterior = {"roof_type": "gable", "roof_color": "red", "floors": 1, "wall_color": "beige", "wall_material": None,
                "window_grid": None, "footprint_width_m": None, "footprint_depth_m": None, "confidence": 0.5, **ext}
    return {"summary": "s", "storeys": [{"name": "Ground", "level": 0, "height_m": None, "rooms": rooms or [room]}],
            "exterior": exterior, "interior_photos": [], "scale_hints": [], "conflicts": [], "open_questions": [],
            "confidence": {"overall": 0.8, "rooms": 0.8, "exterior": 0.5}}


def room(name: str, **kw: Any) -> dict[str, Any]:
    base = analysis()["storeys"][0]["rooms"][0]
    return {**base, "name": name, **kw}
