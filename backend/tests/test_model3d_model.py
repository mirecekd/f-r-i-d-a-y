# backend/tests/test_model3d_model.py
import pytest

from app.model3d.model import MAX_PARTS, Model, ModelError, Part


def _model(*parts):
    return Model.from_dict({"id": "m1", "parts": list(parts)})


def test_round_trip():
    m = _model({"id": "a", "kind": "box", "scale": [2, 1, 1], "tags": ["x"], "props": {"net": "GND"}},
               {"id": "b", "kind": "group", "parent": "a"})
    assert Model.from_dict(m.to_dict()).to_dict() == m.to_dict()
    assert m.parts["a"].props == {"net": "GND"}
    assert m.scale_to_scene == 0.001


def test_duplicate_ids_rejected():
    with pytest.raises(ModelError, match="duplicate"):
        _model({"id": "a"}, {"id": "a"})


def test_missing_parent_rejected():
    with pytest.raises(ModelError, match="does not exist"):
        _model({"id": "a", "parent": "zzz"})


def test_cycle_rejected():
    with pytest.raises(ModelError, match="cycle"):
        _model({"id": "a", "parent": "b"}, {"id": "b", "parent": "a"})


def test_self_parent_rejected():
    with pytest.raises(ModelError, match="cycle"):
        _model({"id": "a", "parent": "a"})


def test_part_cap():
    m = Model("m1")
    m.parts = {f"p{i}": Part(f"p{i}") for i in range(MAX_PARTS + 1)}
    with pytest.raises(ModelError, match="limit"):
        m.validate()


@pytest.mark.parametrize("bad", [
    {"id": "a", "kind": "nope"},
    {"id": "bad id!"},
    {"id": "a", "pos": [1, 2]},
    {"id": "a", "opacity": 2},
    {"id": "a", "tags": "x"},
    {"id": "a", "extra": 1},
    {"id": "a", "kind": "box", "geom": {"pts": []}},
    {"id": "a", "kind": "polyline", "geom": {"color": "red"}},
])
def test_bad_parts_rejected(bad):
    with pytest.raises(ModelError):
        _model(bad)


def test_bad_layer_rejected():
    with pytest.raises(ModelError):
        Model.from_dict({"id": "m1", "layers": {"top": {"bogus": 1}}})
