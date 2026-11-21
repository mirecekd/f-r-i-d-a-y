# backend/tests/test_model3d_measure.py
import pytest

from app.model3d.measure import describe_model, measure
from app.model3d.model import Model, ModelError


def _m():
    return Model.from_dict({"id": "m", "parts": [
        {"id": "g", "kind": "group", "pos": [10, 0, 0], "scale": 2},
        {"id": "a", "kind": "box", "parent": "g", "pos": [1, 0, 0], "tags": ["smd"], "props": {"ref": "R1"}},
        {"id": "b", "kind": "box"},
    ]})


def test_measure_uses_parent_transform():
    r = measure(_m(), "a", "b")
    assert r["distance"] == 12 and r["units"] == "mm"


def test_measure_unknown_part():
    with pytest.raises(ModelError):
        measure(_m(), "a", "zz")


def test_describe_shows_ids_props_and_nesting():
    text = describe_model(_m())
    assert "  - a box" in text and '"ref":"R1"' in text and "tags=smd" in text


def test_describe_truncates():
    m = Model.from_dict({"id": "m", "parts": [{"id": f"p{i}"} for i in range(20)]})
    assert "truncated" in describe_model(m, max_lines=5)
