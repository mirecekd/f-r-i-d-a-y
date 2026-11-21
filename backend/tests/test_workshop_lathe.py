# backend/tests/test_workshop_lathe.py
import json
from pathlib import Path

import pytest

from app.model3d.bounds import model_bounds
from app.model3d.compile import compile_model
from app.model3d.model import Model
from app.scene_schema import check_op
from app.workshop.spec import SpecError, expand, with_params

FIXTURE = Path(__file__).parent / "fixtures" / "workshop" / "vase.json"

EXAMPLES = {
    "bottle": [[0, 0], [30, 0], [30, 150], [12, 190], [12, 240], [0, 240]],
    "pawn": [[0, 0], [20, 0], [14, 10], [8, 40], [14, 50], [6, 55], [12, 70], [12, 85], [0, 95]],
    "wheel_hub": [[0, 0], [60, 0], [60, 20], [25, 20], [25, 50], [0, 50]],
}


def lathe(**kw):
    return {"parts": [{"id": "l", "kind": "lathe", "profile": [[0, 0], [10, 0], [5, 20]], **kw}]}


def test_vase_fixture_expands_and_validates():
    result = expand(json.loads(FIXTURE.read_text()))
    assert [p["kind"] for p in result.parts] == ["lathe"]
    assert result.parts[0]["geom"]["segments"] == 48 and len(result.parts[0]["geom"]["profile"]) == 8
    assert result.parts[0]["geom"]["profile"][2] == [70, pytest.approx(72)]
    model = Model.from_dict({"id": "vase", "units": "mm", "parts": result.parts})
    for op in compile_model(model):
        check_op(op)


@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_examples_expand_to_valid_scene_ops(name):
    result = expand(lathe(profile=EXAMPLES[name]))
    model = Model.from_dict({"id": name, "units": "mm", "parts": result.parts})
    for op in compile_model(model):
        check_op(op)


def test_segments_default_and_range():
    assert expand(lathe()).parts[0]["geom"]["segments"] == 24
    for bad in (2, 97):
        with pytest.raises(SpecError, match=r"parts\[0\]\.segments"):
            expand(lathe(segments=bad))


def test_profile_errors_name_the_field():
    with pytest.raises(SpecError, match=r"parts\[0\]\.profile\[1\]\[0\].*>= 0"):
        expand(lathe(profile=[[1, 0], [-2, 3]]))
    with pytest.raises(SpecError, match=r"profile.*2\.\.64"):
        expand(lathe(profile=[[1, 0]]))
    with pytest.raises(SpecError, match="unknown parameter"):
        expand(lathe(profile=[[1, 0], ["=nope", 3]]))


def test_unknown_key_gets_did_you_mean():
    with pytest.raises(SpecError, match=r"parts\[0\]\.profil: unknown key.*profile"):
        expand({"parts": [{"id": "l", "kind": "lathe", "profil": [[0, 0], [1, 1]]}]})


def test_profile_follows_parameters():
    spec = {"params": {"r": {"value": 10, "min": 1, "max": 50}},
            "parts": [{"id": "l", "kind": "lathe", "profile": [[0, 0], ["=r", 0], [0, 5]]}]}
    assert expand(with_params(spec, {"r": 30})).parts[0]["geom"]["profile"][1] == [30, 0]


def test_mirror_y_flips_the_profile_and_mirror_x_keeps_it():
    spec = lathe(profile=[[0, 1], [5, 2], [3, 8]])
    spec["parts"][0]["mirror"] = "y"
    parts = {p["id"]: p for p in expand(spec).parts}
    assert parts["l.m"]["geom"]["profile"] == [[0, -1], [5, -2], [3, -8]]
    spec["parts"][0]["mirror"] = "x"
    parts = {p["id"]: p for p in expand(spec).parts}
    assert parts["l.m"]["geom"]["profile"] == parts["l"]["geom"]["profile"]


def test_bounds_follow_the_profile():
    result = expand(lathe(profile=[[0, 2], [10, 2], [4, 30]]))
    model = Model.from_dict({"id": "b", "units": "mm", "parts": result.parts})
    box = model_bounds(model)
    assert box is not None
    lo, hi = box
    assert lo == [-10, 2, -10] and hi == [10, 30, 10]
