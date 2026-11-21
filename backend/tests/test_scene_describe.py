# backend/tests/test_scene_describe.py
from app.scene import SceneStore


def test_describe_tree():
    s = SceneStore()
    s.apply([
        {"op": "add", "obj": {"id": "robot", "kind": "group", "pos": [1, 0, 0]}},
        {"op": "add", "obj": {"id": "head", "kind": "sphere", "parent": "robot", "color": "#ff0000", "label": "Head",
                              "anim": {"type": "spin"}}},
        {"op": "add", "obj": {"id": "t", "kind": "text", "text": "hello"}},
        {"op": "camera", "pos": [0, 1, 9]},
    ])
    s.select(["head"])
    out = s.describe().splitlines()
    assert out[0] == "scene: 3 objects; selected: head; camera pos(0,1,9) look(0,0,0)"
    assert out[1] == "robot group pos(1,0,0)"
    assert out[2] == '  *head sphere #ff0000 "Head" anim=spin'
    assert out[3] == 't text text="hello"'


def test_describe_truncates():
    s = SceneStore()
    s.apply([{"op": "add", "obj": {"id": f"o{i}", "kind": "box"}} for i in range(50)])
    out = s.describe(max_lines=10).splitlines()
    assert len(out) == 11
    assert out[-1] == "... 41 more objects"


def test_describe_empty():
    assert SceneStore().describe() == "scene: 0 objects; selected: none"
