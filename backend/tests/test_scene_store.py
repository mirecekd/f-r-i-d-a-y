# backend/tests/test_scene_store.py
import pytest

from app.scene import SceneError, SceneStore


def add(obj: dict) -> dict:
    return {"op": "add", "obj": obj}


def test_add_set_del_roundtrip():
    s = SceneStore()
    s.apply([add({"id": "a", "kind": "box", "pos": [0, 1, 0]})])
    s.apply([{"op": "set", "id": "a", "props": {"color": "#ff0000"}, "ms": 300}])
    assert s.objects()[0]["color"] == "#ff0000"
    s.apply([{"op": "del", "id": "a"}])
    assert s.objects() == []


def test_unknown_kind_rejected():
    with pytest.raises(SceneError, match="unknown kind"):
        SceneStore().apply([add({"id": "a", "kind": "teapot"})])


def test_unknown_prop_rejected_for_kind():
    with pytest.raises(SceneError, match="unknown property 'values'"):
        SceneStore().apply([add({"id": "a", "kind": "box", "values": [1]})])


def test_set_unknown_prop_rejected():
    s = SceneStore()
    s.apply([add({"id": "a", "kind": "box"})])
    with pytest.raises(SceneError, match="unknown property"):
        s.apply([{"op": "set", "id": "a", "props": {"bogus": 1}}])
    with pytest.raises(SceneError, match="unknown property"):
        s.apply([{"op": "set", "id": "a", "props": {"kind": "sphere"}}])


def test_bad_values_rejected():
    s = SceneStore()
    for obj in (
        {"id": "a", "kind": "box", "pos": [1, 2]},
        {"id": "a", "kind": "box", "color": 5},
        {"id": "a", "kind": "box", "anim": {"type": "wobble"}},
        {"id": "a", "kind": "image", "url": "file:///etc/passwd"},
        {"id": "a", "kind": "box", "pos": [float("nan"), 0, 0]},
    ):
        with pytest.raises(SceneError):
            s.apply([add(obj)])
    assert s.objects() == []


def test_unknown_op_and_fields_rejected():
    s = SceneStore()
    with pytest.raises(SceneError, match="unknown op"):
        s.apply([{"op": "nuke"}])
    with pytest.raises(SceneError, match="unknown fields"):
        s.apply([{"op": "clear", "all": True}])


def test_failed_batch_is_atomic():
    s = SceneStore()
    s.apply([add({"id": "keep", "kind": "box"})])
    with pytest.raises(SceneError, match="op #1"):
        s.apply([add({"id": "new", "kind": "box"}), add({"id": "x", "kind": "nope"})])
    assert [o["id"] for o in s.objects()] == ["keep"]


def test_object_cap():
    s = SceneStore()
    s.apply([add({"id": f"o{i}", "kind": "box"}) for i in range(5000)])
    with pytest.raises(SceneError, match="limit"):
        s.apply([add({"id": "one-too-many", "kind": "box"})])
    s.apply([add({"id": "o0", "kind": "sphere"})])  # replacing an id stays within the cap
    assert len(s.objects()) == 5000


def test_del_removes_children():
    s = SceneStore()
    s.apply([add({"id": "g", "kind": "group"}), add({"id": "c", "kind": "box", "parent": "g"}),
             add({"id": "gc", "kind": "box", "parent": "c"}), add({"id": "other", "kind": "box"})])
    s.apply([{"op": "del", "id": "g"}])
    assert [o["id"] for o in s.objects()] == ["other"]


def test_camera_and_explode_state():
    s = SceneStore()
    s.apply([{"op": "camera", "pos": [1, 2, 3]}, {"op": "explode", "factor": 1.5}])
    assert s.camera == {"pos": [1, 2, 3], "look": [0, 0, 0]}
    assert s.explode == 1.5
    s.apply([{"op": "explode", "factor": 0}])
    assert s.explode == 0


def test_selection_filters_unknown_and_follows_deletes():
    s = SceneStore()
    s.apply([add({"id": "a", "kind": "box"}), add({"id": "b", "kind": "box"})])
    s.select(["a", "ghost", "b"])
    assert s.selected == ["a", "b"]
    s.apply([{"op": "del", "id": "a"}])
    assert s.selected == ["b"]
    s.apply([{"op": "clear"}])
    assert s.selected == []


def test_visible_prop_is_boolean_on_every_kind():
    s = SceneStore()
    s.apply([add({"id": "a", "kind": "box", "visible": False}), add({"id": "t", "kind": "text", "text": "x"})])
    s.apply([{"op": "set", "id": "t", "props": {"visible": False}}, {"op": "set", "id": "a", "props": {"visible": True}}])
    assert [o.get("visible") for o in s.objects()] == [True, False]
    with pytest.raises(SceneError, match="visible must be a boolean"):
        s.apply([{"op": "set", "id": "a", "props": {"visible": "no"}}])
