# backend/tests/test_model3d_compile.py
import pytest

from app.model3d.compile import compile_model
from app.model3d.explode import explode
from app.model3d.model import Model, ModelError
from app.scene import SceneStore


def _model():
    return Model.from_dict({
        "id": "pcb",
        "layers": {"copper": {"z_index": 1, "color": "#c80"}, "board": {"z_index": 0, "opacity": 0.5}, "hid": {"visible": False}},
        "parts": [
            {"id": "base", "kind": "box", "layer": "board", "scale": [100, 2, 60], "color": "#0a0"},
            {"id": "trace", "kind": "polyline", "layer": "copper", "pos": [0, 2, 0], "geom": {"pts": [[0, 0, 0], [10, 0, 0]]}},
            {"id": "grp", "kind": "group", "layer": "copper", "pos": [5, 2, 0]},
            {"id": "chip", "kind": "box", "layer": "copper", "parent": "grp", "pos": [1, 0, 0]},
            {"id": "secret", "kind": "box", "layer": "hid"},
        ],
    })


def test_compile_validates_and_applies_layers():
    scene = SceneStore()
    scene.apply([{"op": "add", "obj": {"id": "other", "kind": "box"}}])
    ops = compile_model(_model())
    scene.apply(ops)
    objs = {o["id"]: o for o in scene.objects()}
    assert "other" in objs and "model:pcb" in objs
    assert objs["model:pcb"]["scale"] == pytest.approx(0.04)  # 100 mm board auto-fitted to 4 scene units
    assert objs["m:pcb:chip"]["parent"] == "m:pcb:grp"
    assert objs["m:pcb:chip"]["color"] == "#c80"
    assert objs["m:pcb:base"]["opacity"] == 0.5
    assert "m:pcb:secret" not in objs


def test_recompile_replaces_only_model_group():
    scene = SceneStore()
    scene.apply([{"op": "add", "obj": {"id": "other", "kind": "box"}}])
    m = _model()
    scene.apply(compile_model(m))
    del m.parts["trace"]
    scene.apply(compile_model(m))
    ids = {o["id"] for o in scene.objects()}
    assert "m:pcb:trace" not in ids and "m:pcb:base" in ids and "other" in ids


def test_explode_by_layer_orders_by_z_index():
    m = _model()
    ops = {o["id"]: o["props"]["pos"] for o in explode(m, 1.0, "layer", "y")}
    assert ops["m:pcb:base"][1] == 0
    assert ops["m:pcb:trace"][1] > 2
    assert "m:pcb:chip" not in ops  # follows its parent group
    SceneStore().apply([{"op": "add", "obj": {"id": "m:pcb:base", "kind": "box"}}, *explode(m, 1.0)[:1]])


def test_explode_restore_and_modes():
    m = _model()
    back = {o["id"]: o["props"]["pos"] for o in explode(m, 0)}
    assert back["m:pcb:trace"] == [0, 2, 0]
    assert all(o["ms"] > 0 for o in explode(m, 1))
    radial = {o["id"]: o["props"]["pos"] for o in explode(m, 1, "radial", "y", 10)}
    assert radial["m:pcb:trace"] != [0, 2, 0]
    group = {o["id"]: o["props"]["pos"] for o in explode(m, 1, "group", "x", 10)}
    assert group["m:pcb:trace"][0] == 10
    with pytest.raises(ModelError):
        explode(m, 1, "bogus")
