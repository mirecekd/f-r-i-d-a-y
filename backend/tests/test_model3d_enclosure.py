# backend/tests/test_model3d_enclosure.py
import pytest

from app.model3d.compile import compile_model
from app.model3d.explode import explode
from app.model3d.model import Model, ModelError
from app.model3d.packs import get_pack, list_packs
from app.model3d.packs.enclosure import enclosure_from_spec
from app.model3d.packs.enclosure.build import apply_layers

SPEC = {
    "name": "box", "inner_mm": [60, 40, 20], "wall_mm": 2, "lid": {"type": "snap", "thickness_mm": 2},
    "screw_posts": [{"pos": [x, z], "height_mm": 6, "hole_mm": 2.5, "outer_mm": 6} for x in (-24, 24) for z in (-14, 14)],
    "cutouts": [{"side": "front", "pos": [0, 8], "size": [12, 6], "shape": "rect", "label": "USB"}],
    "vents": {"side": "back", "count": 2, "slot_mm": 1.5},
}


def _model(spec=None, **kw):
    parts = enclosure_from_spec({**(spec or SPEC), **kw})
    m = Model.from_dict({"id": "enc", "scale_to_scene": 0.05, "parts": parts})
    apply_layers(m)
    return m, parts


def test_registered_as_pack():
    assert "enclosure" in list_packs() and get_pack("enclosure") is enclosure_from_spec


def test_part_count_and_layers():
    m, parts = _model()
    layers = {p["layer"] for p in parts}
    assert layers == {"case", "lid", "posts", "cutters"}
    assert sum(p["id"].startswith("post") and p["kind"] == "cylinder" for p in parts) == 4
    assert [p["id"] for p in parts if "cutter" in p.get("tags", []) and p["id"].startswith("cut_")] == [
        "cut_1_USB", "cut_2_vent1", "cut_3_vent2"]
    assert len(parts) == 6 + 6 + 5 + 3 + 4  # shell group+5, lid group+plate+4 lips, posts group+4, 3 cutouts, 4 post holes


def test_cutters_tagged_and_target_existing_parts():
    m, parts = _model()
    ids = {p["id"] for p in parts}
    cutters = [p for p in parts if "cutter" in p.get("tags", [])]
    assert len(cutters) == 3 + 4
    for c in cutters:
        assert c["layer"] == "cutters" and c["props"]["subtract_from"] in ids


def test_layer_z_index_and_explode_lifts_lid():
    m, _ = _model()
    z = [m.layer(n)["z_index"] for n in ("case", "posts", "lid", "cutters")]
    assert z == sorted(z) and len(set(z)) == 4
    ops = {o["id"]: o["props"]["pos"] for o in explode(m, 1.0, by="layer", axis="y", spacing=30)}
    assert ops["m:enc:lid"][1] - m.parts["lid"].pos[1] == 60 and ops["m:enc:posts"][1] == 30


def test_compile_validates_with_and_without_csg():
    m, _ = _model()
    assert not any(o.get("obj", {}).get("kind") == "csg" for o in compile_model(m))
    m2, parts = _model(use_csg=True, model_id="enc")
    csgs = [o["obj"] for o in compile_model(m2) if o.get("obj", {}).get("kind") == "csg"]
    assert {c["id"] for c in csgs} >= {"m:enc:csg_shell", "m:enc:csg_post1"}
    shell = next(c for c in csgs if c["id"] == "m:enc:csg_shell")
    assert shell["op"] == "subtract" and shell["a"] == "m:enc:shell" and "m:enc:cut_1_USB" in shell["b"] and shell["hide_inputs"] is True


@pytest.mark.parametrize("patch", [
    {"inner_mm": [60, -1, 20]}, {"inner_mm": [60, 40]}, {"wall_mm": 0}, {"lid": {"type": "glue"}},
    {"cutouts": [{"side": "front", "pos": [40, 8], "size": [12, 6]}]},  # beyond the wall width
    {"cutouts": [{"side": "front", "pos": [0, 19], "size": [12, 6]}]},  # above the wall
    {"cutouts": [{"side": "front", "pos": [0, 8], "size": [0, 6]}]},
    {"cutouts": [{"side": "nowhere", "pos": [0, 8], "size": [1, 1]}]},
    {"screw_posts": [{"pos": [40, 0], "outer_mm": 6}]},
    {"screw_posts": [{"pos": [0, 0], "outer_mm": 3, "hole_mm": 3}]},
    {"vents": {"side": "back", "count": 0}},
    {"use_csg": True},
])
def test_invalid_specs_raise(patch):
    with pytest.raises(ModelError):
        enclosure_from_spec({**SPEC, **patch})


def test_fit_to_part_uses_bounding_box(tmp_path, monkeypatch):
    monkeypatch.setenv("FRIDAY_DATA_DIR", str(tmp_path))
    from app.model3d.store import ModelStore
    st = ModelStore()
    pcb = st.create("pcb")
    pcb.parts["board"] = pcb.parts.get("board") or __import__("app.model3d.model", fromlist=["Part"]).Part(
        "board", kind="box", pos=[0, 1, 0], scale=[50, 2, 30], layer="board")
    st.save(pcb)
    parts = enclosure_from_spec({"fit_to_part": {"model": "pcb", "part_ids": ["board"], "margin_mm": 2}})
    wall_front = next(p for p in parts if p["id"] == "wall_front")
    assert wall_front["scale"][0] == 54 + 2 * 2  # width 50+2*2 inner plus two walls
    with pytest.raises(ModelError):
        enclosure_from_spec({"fit_to_part": {"model": "pcb", "part_ids": ["nope"]}})
