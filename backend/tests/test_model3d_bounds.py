# backend/tests/test_model3d_bounds.py
import math

import pytest

from app.model3d.bounds import Bounds, changed_substantially, effective_scale, frame_op, longest_side, model_bounds
from app.model3d.compile import compile_model
from app.model3d.model import Model


def _bounds(m: Model) -> Bounds:
    b = model_bounds(m)
    assert b is not None
    return b


def _board(**kw):
    return Model.from_dict({"id": "b", "parts": [
        {"id": "base", "kind": "box", "scale": [100, 2, 60]},
        {"id": "chip", "kind": "box", "pos": [20, 3, 0], "scale": [10, 4, 10]},
    ], **kw})


def test_bounds_include_pos_and_size():
    lo, hi = _bounds(_board())
    assert lo == pytest.approx([-50, -1, -30]) and hi == pytest.approx([50, 5, 30])


def test_bounds_follow_parent_transform_and_rotation():
    m = Model.from_dict({"id": "r", "parts": [
        {"id": "g", "kind": "group", "pos": [10, 0, 0], "rot": [0, math.pi / 2, 0]},
        {"id": "bar", "kind": "box", "parent": "g", "scale": [10, 2, 2]},
    ]})
    lo, hi = _bounds(m)
    assert hi[2] - lo[2] == pytest.approx(10) and hi[0] - lo[0] == pytest.approx(2)
    assert (lo[0] + hi[0]) / 2 == pytest.approx(10)


def test_bounds_polyline_and_extrude_use_geom():
    m = Model.from_dict({"id": "p", "parts": [
        {"id": "l", "kind": "polyline", "geom": {"pts": [[0, 0, 0], [30, 0, 0]]}},
        {"id": "e", "kind": "extrude", "geom": {"outline": [[0, 0], [5, 0], [0, 50]], "height": 2}},
    ]})
    assert longest_side(_bounds(m)) >= 50


def test_empty_or_hidden_has_no_bounds():
    assert model_bounds(Model("e")) is None
    m = _board()
    m.parts["base"].visible = False
    m.parts["chip"].visible = False
    assert model_bounds(m) is None


def test_auto_fit_scales_tiny_and_huge_but_not_mid_models():
    assert effective_scale(_board()) == pytest.approx(4 / 100)
    assert effective_scale(_board(auto_fit=False)) == 0.001
    mid = Model.from_dict({"id": "m", "units": "m", "scale_to_scene": 1.0, "parts": [{"id": "a", "kind": "box", "scale": [5, 1, 1]}]})
    assert effective_scale(mid) == 1.0
    assert effective_scale(Model("empty")) == 0.001


def test_compile_root_uses_fitted_scale_and_model_keeps_true_scale():
    m = _board()
    assert compile_model(m)[1]["obj"]["scale"] == pytest.approx(0.04)
    assert m.scale_to_scene == 0.001 and Model.from_dict(m.to_dict()).auto_fit is True


def test_frame_op_looks_at_centre_from_a_distance_covering_the_radius():
    m = _board()
    op = frame_op(m, _bounds(m))
    assert op["op"] == "camera"
    k = 0.04
    assert op["look"] == pytest.approx([0, 2 * k, 0], abs=1e-3)
    assert math.dist(op["pos"], op["look"]) > 2 * 60 * k  # farther than the bounding radius


def test_changed_substantially():
    a: Bounds = ([0.0, 0.0, 0.0], [10.0, 1.0, 1.0])
    assert changed_substantially(None, a)
    assert not changed_substantially(a, ([0.0, 0.0, 0.0], [11.0, 1.0, 1.0]))
    assert changed_substantially(a, ([0.0, 0.0, 0.0], [30.0, 1.0, 1.0]))
    assert not changed_substantially(a, None)
