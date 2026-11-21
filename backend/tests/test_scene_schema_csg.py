# backend/tests/test_scene_schema_csg.py
import pytest

from app.scene_schema import SceneError, check_op


def _csg(**props):
    return {"op": "add", "obj": {"id": "c", "kind": "csg", "op": "subtract", "a": "shell", "b": ["cut1"], "hide_inputs": True, **props}}


def test_csg_kind_accepts_operands():
    check_op(_csg())


@pytest.mark.parametrize("bad", [{"b": "cut1"}, {"a": 3}, {"hide_inputs": "yes"}, {"op": 1}])
def test_csg_kind_rejects_bad_types(bad):
    with pytest.raises(SceneError):
        check_op(_csg(**bad))
