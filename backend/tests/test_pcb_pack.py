# backend/tests/test_pcb_pack.py
import pytest

from app.model3d.changes import apply_changes
from app.model3d.compile import compile_model
from app.model3d.explode import explode
from app.model3d.model import Model, ModelError, Part
from app.model3d.packs import get_pack, list_packs, load_all
from app.model3d.packs.pcb import (
    pcb_from_spec,
    pcb_layer_settings,
    pcb_trace_diff_helper,
)
from app.model3d.packs.pcb.layers import Z_INDEX
from app.scene_schema import check_op

ALL_KINDS = ["resistor", "capacitor", "led", "soic", "qfp", "pin_header", "usb_c", "crystal", "esp32_module", "generic"]


def _spec(**over):
    spec = {
        "name": "demo", "size_mm": [60, 40], "layers": 2,
        "components": [
            {"ref": "R1", "kind": "resistor", "value": "10k", "footprint": "0603", "pos": [10, 10], "nets": {"1": "VCC", "2": "SIG"}},
            {"ref": "C1", "kind": "capacitor", "footprint": "0805", "pos": [10, 20], "rot": 90},
            {"ref": "D1", "kind": "led", "value": "green", "pos": [20, 10]},
            {"ref": "U1", "kind": "soic", "pos": [30, 20]},
            {"ref": "J1", "kind": "pin_header", "pos": [50, 20], "pins": 4},
        ],
        "traces": [{"net": "SIG", "layer": "top", "width_mm": 0.3, "points": [[10, 10], [15, 10], [15, 20]]},
                   {"net": "GND", "layer": "bottom", "width_mm": 0.5, "points": [[5, 5], [55, 5]]}],
        "vias": [{"pos": [15, 20], "drill_mm": 0.3, "net": "SIG"}],
    }
    spec.update(over)
    return spec


def _model(spec=None):
    return Model.from_dict({"id": "pcb1", "parts": pcb_from_spec(spec or _spec()), "layers": pcb_layer_settings()})


def test_pack_is_registered_via_load_all():
    load_all()
    assert "pcb" in list_packs() and get_pack("pcb") is pcb_from_spec


@pytest.mark.parametrize("bad", [
    {"components": [{"ref": "X", "kind": "toaster", "pos": [1, 1]}]},
    {"components": [{"ref": "X", "kind": "resistor", "pos": [100, 1]}]},
    {"components": [{"ref": "X", "kind": "resistor", "pos": [1, 1]}, {"ref": "X", "kind": "led", "pos": [2, 2]}]},
    {"traces": [{"net": "A", "layer": "inner1", "width_mm": 0.2, "points": [[1, 1], [2, 2]]}]},
    {"traces": [{"net": "A", "layer": "top", "width_mm": 0.2, "points": [[1, 1], [2, 99]]}]},
    {"vias": [{"pos": [-1, 2], "drill_mm": 0.3}]},
    {"size_mm": [0, 10]},
    {"layers": 3},
])
def test_bad_spec_is_an_error(bad):
    with pytest.raises(ModelError):
        pcb_from_spec(_spec(**bad))


def test_part_counts_and_required_layers():
    parts = pcb_from_spec(_spec())
    ids = {p["id"] for p in parts}
    assert len(ids) == len(parts)
    assert {"board", "mask_top", "comp_R1", "comp_U1", "comp_J1", "via1", "trace_SIG_1", "trace_GND_1"} <= ids
    assert sum(p["id"].startswith("pad_") for p in parts) == 2 + 2 + 2 + 8 + 4
    assert {p["layer"] for p in parts} >= {"board", "copper_top", "copper_bottom", "mask_top", "components", "vias"}
    groups = [p for p in parts if p["id"] in ("comp_R1", "comp_C1", "comp_D1", "comp_U1", "comp_J1")]
    assert len(groups) == 5 and all(g["props"]["ref"] for g in groups)
    assert next(p for p in parts if p["id"] == "comp_R1")["props"] == {
        "ref": "R1", "value": "10k", "footprint": "0603", "kind": "resistor", "side": "top",
        "nets": {"1": "VCC", "2": "SIG"}, "net": "SIG,VCC"}


def test_four_layer_board_has_inner_planes_and_inner_traces():
    spec = _spec(layers=4, traces=[{"net": "P", "layer": "inner1", "width_mm": 0.4, "points": [[5, 5], [20, 5]]}])
    parts = pcb_from_spec(spec)
    layers = {p["layer"] for p in parts}
    assert {"inner1", "inner2"} <= layers
    assert any(p["id"] == "plane_inner2" for p in parts)


def test_layer_z_index_ordering():
    z = pcb_layer_settings()
    assert z["copper_bottom"]["z_index"] < z["inner2"]["z_index"] < z["inner1"]["z_index"] < z["board"]["z_index"]
    assert z["board"]["z_index"] < z["copper_top"]["z_index"] < z["mask_top"]["z_index"] < z["silk_top"]["z_index"] < z["components"]["z_index"]
    model = _model()
    ops = explode(model, 1.0, by="layer", axis="y")
    ys = {op["id"]: op["props"]["pos"][1] for op in ops}
    top = ys["m:pcb1:comp_R1"] - model.parts["comp_R1"].pos[1]
    base = ys["m:pcb1:board"] - model.parts["board"].pos[1]
    bot = ys["m:pcb1:trace_GND_1"] - model.parts["trace_GND_1"].pos[1]
    assert top > base > bot
    assert Z_INDEX["components"] == max(Z_INDEX.values())


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_every_kind_builds_valid_parts(kind):
    comp = {"ref": "X1", "kind": kind, "pos": [30, 20], "side": "bottom" if kind == "led" else "top"}
    parts = pcb_from_spec(_spec(components=[comp], traces=[], vias=[]))
    for p in parts:
        Part.from_dict(p).check()
    assert any(p["id"] == "comp_X1" for p in parts)


@pytest.mark.parametrize("kind,pins", [("soic", 14), ("soic", 16), ("qfp", 32), ("qfp", 44), ("qfp", 64), ("pin_header", 10)])
def test_pin_counts(kind, pins):
    parts = pcb_from_spec(_spec(components=[{"ref": "U", "kind": kind, "pos": [30, 20], "pins": pins}], traces=[], vias=[]))
    assert sum(p["id"].startswith("pad_U_") for p in parts) == pins


def test_bad_pin_count_is_an_error():
    with pytest.raises(ValueError):
        pcb_from_spec(_spec(components=[{"ref": "U", "kind": "qfp", "pos": [30, 20], "pins": 33}]))


def test_compile_validates_against_scene_schema():
    model = _model(_spec(layers=4, silk=[{"text": "REV A", "pos": [30, 35]}], outline=[[0, 0], [60, 0], [60, 40], [0, 40]]))
    ops = compile_model(model)
    assert ops[0] == {"op": "del", "id": "model:pcb1"} and len(ops) == len(model.parts) + 2
    for op in ops:
        check_op(op)


def test_trace_diff_helper_removes_old_and_adds_new():
    model = _model()
    new_pts = [[10, 10], [10, 25], [15, 25]]
    changes = pcb_trace_diff_helper(_spec(), "SIG", new_pts)
    removed = [c["id"] for c in changes if c["op"] == "remove"]
    assert removed == ["trace_SIG_1"]
    added = [c["part"] for c in changes if c["op"] == "add"]
    assert added[0]["id"] == "trace_SIG_rev" and added[0]["props"]["points"] == new_pts
    assert added[0]["layer"] == "copper_top" and added[0]["props"]["width_mm"] == 0.3
    assert len(added) == 1 + 2 + 1  # group, two segments, one joint
    after = apply_changes(model, changes)
    assert "trace_SIG_1" not in after.parts and "trace_SIG_1_s1" not in after.parts
    assert "trace_SIG_rev_s2" in after.parts and "trace_GND_1" in after.parts
    for op in compile_model(after):
        check_op(op)


def test_trace_diff_helper_rejects_out_of_bounds_and_unknown_net_defaults():
    with pytest.raises(ModelError):
        pcb_trace_diff_helper(_spec(), "SIG", [[1, 1], [500, 1]])
    changes = pcb_trace_diff_helper(_spec(), "NEW", [[1, 1], [9, 9]])
    assert [c["op"] for c in changes] == ["add", "add"]
