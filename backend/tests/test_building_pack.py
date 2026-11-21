# backend/tests/test_building_pack.py
import math

import pytest

from app.model3d.compile import compile_model
from app.model3d.explode import explode
from app.model3d.model import Model, Part
from app.model3d.packs import get_pack, list_packs
from app.model3d.packs.building import (
    BuildingSpecError,
    building_from_spec,
    building_scale_to_room,
    layer_defs,
    plan_to_spec,
)
from app.model3d.packs.building.plan import parse_dimensions
from app.model3d.packs.building.spec import normalize
from app.model3d.packs.building.walls import wall_list

SPEC = {
    "name": "flat",
    "storeys": [{
        "name": "Ground",
        "rooms": [{"id": "kit", "name": "Kuchyn", "rect": [0, 0, 4, 5]}, {"id": "liv", "name": "Obyvak", "rect": [4, 0, 3.5, 5]},
                  {"id": "bed", "name": "Loznice", "rect": [0, 5, 7.5, 3]}],
        "openings": [{"room": "kit", "side": "e", "kind": "door", "offset": 1}, {"room": "bed", "side": "n", "kind": "door", "offset": 5},
                     {"room": "kit", "side": "n", "kind": "window", "offset": 1.4}, {"room": "liv", "side": "n", "kind": "window", "offset": 1},
                     {"room": "bed", "side": "s", "kind": "window", "offset": 3}],
        "furniture": [{"kind": "bed", "room": "bed"}, {"kind": "sofa", "room": "liv", "rot": 90}, {"kind": "table", "pos": [2, 2]}],
    }],
    "roof": {"type": "gable", "overhang": 0.4},
}


def _model(parts):
    return Model.from_dict({"id": "b", "units": "m", "parts": parts, "layers": layer_defs(parts)})


def test_pack_is_registered_and_parts_are_valid():
    assert "building" in list_packs()
    pack = get_pack("building")
    assert pack is not None
    parts = pack(SPEC)
    for p in parts:
        Part.from_dict(p)
    assert len({p["id"] for p in parts}) == len(parts)


def test_part_counts_by_kind():
    parts = building_from_spec(SPEC)
    count = lambda kind: sum(1 for p in parts if p["props"].get("kind") == kind and p["kind"] == "group")
    assert count("storey") == 1
    assert sum(1 for p in parts if p["props"].get("opening") == "door" and p["kind"] == "group") == 2
    assert sum(1 for p in parts if p["props"].get("opening") == "window" and p["kind"] == "group") == 3
    assert sum(1 for p in parts if p["props"].get("kind") == "floor") == 3
    assert sum(1 for p in parts if p["kind"] == "text") == 3
    assert count("furniture") == 3
    assert {"roof", "roof-slope-e", "roof-slope-w", "roof-gable-s", "roof-gable-n"} <= {p["id"] for p in parts}


def test_shared_edges_yield_one_wall():
    st = normalize(SPEC)["storeys"][0]
    walls = wall_list(st)
    keys = {tuple(sorted((tuple(w["a"]), tuple(w["b"])))) for w in walls}
    assert len(keys) == len(walls)
    # kit|liv share x=4 over y 0..5, bed spans x 0..7.5 at y=5: its north edge splits at x=4
    assert sum(1 for w in walls if w["a"][0] == w["b"][0] == 4 and {w["a"][1], w["b"][1]} == {0, 5}) == 1
    assert sum(1 for w in walls if w["a"][1] == w["b"][1] == 5) == 2
    assert len(walls) == 10


def test_openings_stay_inside_their_wall():
    parts = {p["id"]: p for p in building_from_spec(SPEC)}
    for p in parts.values():
        if p["props"].get("opening") and p["kind"] == "group":
            wall = parts[f"ground-wall-{p['props']['wall']}"]
            half = p["props"]["width"] / 2
            assert abs(_local_x(p, wall)) + half <= wall["props"]["length"] / 2 + 1e-3
            assert p["pos"][1] - p["props"]["height"] / 2 >= -1e-6


def _local_x(opening, wall):
    """x of the opening centre in the wall's local frame (yaw about y turns local +x to (cos, -sin))."""
    dx, dz = opening["pos"][0] - wall["pos"][0], opening["pos"][2] - wall["pos"][2]
    yaw = wall["rot"][1]
    return dx * math.cos(yaw) - dz * math.sin(yaw)


def test_wall_pieces_leave_a_gap_for_the_opening():
    parts = building_from_spec(SPEC)
    door_wall = next(p for p in parts if p["props"].get("opening") == "door")["props"]["wall"]
    pieces = [p for p in parts if p["parent"] == f"ground-wall-{door_wall}"]
    assert len(pieces) >= 2


def test_opening_errors():
    bad = {"storeys": [{"rooms": [{"id": "a", "rect": [0, 0, 2, 2]}], "openings": [{"room": "a", "side": "n", "kind": "door", "offset": 1.5}]}]}
    with pytest.raises(BuildingSpecError, match="does not fit"):
        building_from_spec(bad)
    bad["storeys"][0]["openings"] = [{"room": "a", "side": "n", "kind": "window", "offset": 0.2, "height": 2.5}]
    with pytest.raises(BuildingSpecError, match="taller"):
        building_from_spec(bad)


@pytest.mark.parametrize("spec", [None, {}, {"storeys": []}, {"storeys": [{"rooms": []}]}, {"storeys": [{"rooms": [{"id": "a"}]}]},
                                  {"storeys": [{"rooms": [{"rect": [0, 0, -1, 2]}]}]},
                                  {"storeys": [{"rooms": [{"id": "a", "rect": [0, 0, 1, 1]}, {"id": "a", "rect": [2, 0, 1, 1]}]}]},
                                  {"units": "mm", "storeys": [{"rooms": [{"rect": [0, 0, 1, 1]}]}]}])
def test_spec_validation(spec):
    with pytest.raises(BuildingSpecError):
        building_from_spec(spec)


def test_compile_validates_and_explode_separates_storeys():
    spec = {"storeys": [{"name": "Ground", "rooms": [{"id": "a", "rect": [0, 0, 4, 4]}]},
                        {"name": "Upper", "rooms": [{"id": "b", "rect": [0, 0, 4, 4]}]}], "roof": {"type": "flat"}}
    parts = building_from_spec(spec)
    assert next(p for p in parts if p["id"] == "storey-upper")["pos"][1] == pytest.approx(2.7)
    model = _model(parts)
    ops = compile_model(model)
    assert len(ops) == len(parts) + 2
    z = {name: lay["z_index"] for name, lay in model.layers.items()}
    assert z["ground.walls"] < z["upper.floor"] and z["upper.floor"] < z["roof"]
    assert {p["props"]["storey"] for p in parts} == {"ground", "upper", "roof"}
    assert len(explode(model, 1.0, by="layer")) > 0 and len(explode(model, 1.0, by="group")) == 3


def test_full_spec_compiles():
    assert len(compile_model(_model(building_from_spec(SPEC)))) > 80


def test_polygon_room_uses_extrude_floor():
    spec = {"storeys": [{"rooms": [{"id": "l", "polygon": [[0, 0], [4, 0], [4, 2], [2, 2], [2, 4], [0, 4]]}]}]}
    parts = building_from_spec(spec)
    assert next(p for p in parts if p["id"].endswith("floor-l"))["kind"] == "extrude"
    assert len([p for p in parts if p["props"].get("kind") == "walls" and p["kind"] == "group"]) == 6
    compile_model(_model(parts))


def test_scale_to_room():
    scaled = building_scale_to_room(SPEC, "kit", 6)
    kit = next(r for r in scaled["storeys"][0]["rooms"] if r["id"] == "kit")
    assert kit["polygon"][1][0] - kit["polygon"][0][0] == pytest.approx(6)
    assert next(r for r in scaled["storeys"][0]["rooms"] if r["id"] == "liv")["polygon"][0][0] == pytest.approx(6)
    assert scaled["storeys"][0]["furniture"][2]["pos"] == [3.0, 3.0]
    building_from_spec(scaled)  # still valid, openings still fit
    small = building_scale_to_room(SPEC, "kit", 1.5)
    building_from_spec(small)
    assert SPEC["storeys"][0]["rooms"][0]["rect"] == [0, 0, 4, 5]
    with pytest.raises(BuildingSpecError):
        building_scale_to_room(SPEC, "nope", 3)
    with pytest.raises(BuildingSpecError):
        building_scale_to_room(SPEC, "kit", 0)


def test_plan_to_spec_sample():
    spec = plan_to_spec({"kind": "floorplan", "rooms": [{"name": "Kuchyn", "dimensions": "4.6 x 5.2 m"}, {"name": "Obyvak", "dimensions": "3.6 x 5.2 m"}]})
    rooms = spec["storeys"][0]["rooms"]
    assert [r["rect"] for r in rooms] == [[0, 0, 4.6, 5.2], [4.6, 0, 3.6, 5.2]]
    assert [r["id"] for r in rooms] == ["kuchyn", "obyvak"]
    parts = building_from_spec(spec)
    assert sum(1 for p in parts if p["kind"] == "text") == 2


def test_plan_to_spec_wraps_and_defaults():
    spec = plan_to_spec({"rooms": [{"name": "A", "dimensions": "7 x 3"}, {"name": "B", "dimensions": "6 m x 4 m"}, {"name": "A", "dimensions": None}, "Hall"]})
    rects = [r["rect"] for r in spec["storeys"][0]["rooms"]]
    assert rects[1] == [0, 3, 6, 4]  # wrapped under the first row
    assert rects[2][2:] == [3.5, 4.0] and len({r["id"] for r in spec["storeys"][0]["rooms"]}) == 4
    with pytest.raises(BuildingSpecError):
        plan_to_spec({"rooms": []})


def test_parse_dimensions():
    assert parse_dimensions("4,6 × 5,2 m") == (4.6, 5.2)
    assert parse_dimensions("460 x 520 cm") == (4.6, 5.2)
    assert parse_dimensions("460x520") == (4.6, 5.2)
    assert parse_dimensions("big") is None and parse_dimensions(None) is None
