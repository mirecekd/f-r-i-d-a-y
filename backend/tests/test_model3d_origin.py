# backend/tests/test_model3d_origin.py
import pytest

from app.model3d.compile import compile_model, root_id
from app.model3d.model import Model, ModelError


def _model(origin=None) -> Model:
    d = {"id": "w", "parts": [{"id": "a", "kind": "box"}]}
    if origin is not None:
        d["origin"] = origin
    return Model.from_dict(d)


def test_default_origin_is_not_emitted():
    m = _model()
    assert m.origin == (0.0, 0.0, 0.0)
    assert "origin" not in m.to_dict()
    root = compile_model(m)[1]["obj"]
    assert root["id"] == root_id(m) and "pos" not in root


def test_origin_moves_only_the_root_group_and_roundtrips():
    m = _model([0, 0, 400])
    assert compile_model(m)[1]["obj"]["pos"] == [0.0, 0.0, 400.0]
    assert Model.from_dict(m.to_dict()).origin == (0.0, 0.0, 400.0)
    part_ops = compile_model(m)[2:]
    assert all("pos" not in op["obj"] or op["obj"]["pos"] == [0, 0, 0] for op in part_ops)


@pytest.mark.parametrize("bad", ["x", [1, 2], [1, 2, "3"], [1, 2, True]])
def test_bad_origin_is_refused(bad):
    with pytest.raises(ModelError):
        _model(bad)
