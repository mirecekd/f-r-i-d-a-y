# backend/tests/test_scene_schema_lathe.py
import pytest

from app.scene_schema import SceneError, check_op

PROFILE = [[0, 0], [2, 0], [1, 3], [0, 3]]


def _lathe(**props):
    return {"op": "add", "obj": {"id": "v", "kind": "lathe", "profile": PROFILE, "segments": 32, "cap": True, **props}}


def test_lathe_accepts_valid_props():
    check_op(_lathe())
    check_op({"op": "add", "obj": {"id": "v", "kind": "lathe", "profile": PROFILE}})
    check_op({"op": "set", "id": "v", "props": {"segments": 3, "cap": False}})


@pytest.mark.parametrize("bad", [
    {"profile": [[1, 1]]},
    {"profile": [[1, 1]] * 65},
    {"profile": "abc"},
    {"profile": [[-1, 0], [1, 1]]},
    {"profile": [[1, 0, 3], [1, 1]]},
    {"profile": [[1, "a"], [1, 1]]},
    {"profile": [[1, float("inf")], [1, 1]]},
    {"profile": [[1, float("nan")], [1, 1]]},
    {"profile": [[1, 1e4], [1, 1]]},
    {"profile": [[True, 0], [1, 1]]},
    {"segments": 2},
    {"segments": 97},
    {"segments": 8.5},
    {"segments": "8"},
    {"cap": "yes"},
    {"bogus": 1},
])
def test_lathe_rejects_bad_props(bad):
    with pytest.raises(SceneError):
        check_op(_lathe(**bad))


def test_profile_not_allowed_on_other_kinds():
    with pytest.raises(SceneError):
        check_op({"op": "add", "obj": {"id": "b", "kind": "box", "profile": PROFILE}})
