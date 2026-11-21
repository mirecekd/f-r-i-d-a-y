# backend/tests/test_workshop_fixtures.py
import json
from pathlib import Path

import pytest

from app.model3d.compile import compile_model
from app.model3d.model import Model
from app.scene_schema import check_op
from app.workshop.spec import expand, with_params

FIXTURES = Path(__file__).parent / "fixtures" / "workshop"
NAMES = ["chair", "desk_fan", "robot"]


def load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text())


@pytest.mark.parametrize("name", NAMES)
def test_fixture_expands_into_a_valid_model_and_scene(name):
    result = expand(load(name))
    assert 8 <= len(result.parts) < 60
    assert result.params and not result.notes
    model = Model.from_dict({"id": name, "units": "mm", "parts": result.parts})
    ops = compile_model(model)
    for op in ops:
        check_op(op)
    assert len(ops) == len(result.parts) + 2


@pytest.mark.parametrize("name", NAMES)
def test_first_parameter_changes_the_expansion(name):
    spec = load(name)
    base = expand(spec)
    p = base.params[0]
    changed = expand(with_params(spec, {p["name"]: p["max"]}))
    assert changed.parts != base.parts


def test_robot_is_symmetric():
    parts = {p["id"]: p for p in expand(load("robot")).parts}
    for pid in ("arm", "leg", "eye"):
        a, b = parts[pid], parts[f"{pid}.m"]
        assert b["pos"][0] == pytest.approx(-a["pos"][0]) and b["pos"][1:] == a["pos"][1:]
    assert parts["upper_arm.m"]["parent"] == "arm.m"


def test_fan_blade_count_follows_the_spec():
    ids = [p["id"] for p in expand(load("desk_fan")).parts if p["id"].startswith("blade.")]
    assert ids == [f"blade.{i}" for i in range(5)]
