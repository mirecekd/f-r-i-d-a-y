# backend/app/model3d/packs/building/__init__.py
"""Building / interior pack: rooms, walls with doors and windows, furniture and a roof from one spec."""

from typing import Any

from app.model3d.packs import register_pack
from app.model3d.packs.building.build import building_from_spec, layer_defs
from app.model3d.packs.building.plan import plan_to_spec
from app.model3d.packs.building.scale import building_scale_to_room
from app.model3d.packs.building.spec import BuildingSpecError


def _defaults(spec: dict[str, Any]) -> dict[str, Any]:
    """A two-room ground floor 8 x 4 m with a door, a window and a gable roof (units are metres)."""
    return {"name": "house", "storeys": [{"name": "Ground", "rooms": [
        {"id": "living", "name": "Living room", "rect": [0, 0, 5, 4]}, {"id": "kitchen", "name": "Kitchen", "rect": [5, 0, 3, 4]}],
        "openings": [{"room": "living", "side": "s", "kind": "door", "offset": 1.5}, {"room": "living", "side": "n", "kind": "window", "offset": 1.5}]}],
        "roof": {"type": "gable", "overhang": 0.4}}


_EXAMPLE = {"storeys": [{"name": "Ground", "rooms": [{"id": "a", "name": "Living room", "rect": [0, 0, 5, 4]}]}], "roof": {"type": "gable"}}
register_pack("building", building_from_spec, example=_EXAMPLE, defaults=_defaults, units="m", layers=layer_defs)

__all__ = ["BuildingSpecError", "building_from_spec", "building_scale_to_room", "layer_defs", "plan_to_spec"]
