# backend/tests/test_workshop_stage.py
"""Workshop stage: ids, schema validity, origin placement, table radius and camera poses."""

from app.scene import SceneStore
from app.scene_schema import check_op
from app.workshop import stage
from app.workshop.spec import expand

WID = "abc012abc012"
ORIGIN = (0.0, 0.0, 400.0)
CHAIR = {
    "parts": [
        {"id": "seat", "kind": "box", "size": [400, 40, 400], "pos": [0, 400, 0]},
        {"id": "leg", "kind": "box", "size": [40, 400, 40], "pos": [180, 200, 180]},
    ]
}


def _model(spec=CHAIR):
    return stage.build_model(WID, expand(spec).parts, "mm", ORIGIN)


def test_stage_ops_validate_use_ws_ids_and_apply_to_a_scene():
    ops = stage.stage_ops(WID, "Chair", ORIGIN, 4.0, 1.5)
    for op in ops:
        check_op(op)
    ids = [o["obj"]["id"] for o in ops if o["op"] == "add"]
    assert ids and all(i.startswith(f"ws:{WID}:") for i in ids)
    assert ops[0] == {"op": "del", "id": f"ws:{WID}:stage"}
    scene = SceneStore()
    scene.apply(ops)
    scene.apply(ops)  # redrawing replaces, never duplicates
    assert len(scene.objects()) == len(ids)
    assert next(o for o in scene.objects() if o["id"] == f"ws:{WID}:stage")["pos"] == list(ORIGIN)


def test_model_ops_put_the_root_at_the_origin_and_ids_do_not_collide_with_the_stage():
    ops = stage.model_ops(_model())
    root = ops[1]["obj"]
    assert root["pos"] == list(ORIGIN) and root["id"] == stage.root_of(WID)
    scene = SceneStore()
    scene.apply(ops + stage.stage_ops(WID, "x", ORIGIN, 3.0, 1.0))
    assert len(scene.objects()) == len(ops) - 1 + 4


def test_table_radius_adapts_with_a_floor_and_a_ceiling():
    assert stage.table_radius(None, 1.0) == 3.0
    assert stage.table_radius(([-0.1, 0, -0.1], [0.1, 1, 0.1]), 1.0) == 3.0
    assert 5.0 <= stage.table_radius(([-4, 0, -4], [4, 1, 4]), 1.0) <= 8.0
    assert stage.table_radius(([-9999, 0, -9999], [9999, 1, 9999]), 1.0) == stage.MAX_RADIUS


def test_camera_is_near_the_origin_and_looks_at_the_model():
    model = _model()
    bounds, scale = stage.model_extent(model)
    radius = stage.table_radius(bounds, scale)
    cam = stage.camera_op(model, bounds, ORIGIN, radius)
    check_op(cam)
    assert abs(cam["look"][2] - 400) < 5 and abs(cam["pos"][2] - 400) < 30 + radius * 3
    empty = stage.camera_op(None, None, ORIGIN, 3.0)
    check_op(empty)
    assert empty["pos"][2] > 400 and empty["look"][2] == 400


def test_a_bad_part_is_a_model_error():
    import pytest

    from app.model3d.model import ModelError

    with pytest.raises(ModelError):
        stage.build_model(WID, [{"id": "a", "kind": "nope"}], "mm", ORIGIN)
