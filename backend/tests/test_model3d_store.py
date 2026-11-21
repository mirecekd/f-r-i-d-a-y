# backend/tests/test_model3d_store.py
import pytest

from app.model3d.model import Model, ModelError, Part
from app.model3d.store import MAX_HISTORY, ModelStore


def _edit(store, mid, pid):
    before = store.load(mid)
    after = Model.from_dict(before.to_dict())
    after.parts[pid] = Part(pid, "box")
    store.commit(before, after)


def test_create_persist_round_trip(tmp_path):
    s = ModelStore(tmp_path)
    s.create("pcb", "mm")
    _edit(s, "pcb", "a")
    assert ModelStore(tmp_path).load("pcb").parts.keys() == {"a"}
    assert s.list() == ["pcb"]
    assert not list(tmp_path.glob("*.tmp"))


def test_create_twice_and_bad_id(tmp_path):
    s = ModelStore(tmp_path)
    s.create("m")
    with pytest.raises(ModelError):
        s.create("m")
    with pytest.raises(ModelError):
        s.load("../etc")


def test_undo_redo(tmp_path):
    s = ModelStore(tmp_path)
    s.create("m")
    _edit(s, "m", "a")
    _edit(s, "m", "b")
    assert s.undo("m").parts.keys() == {"a"}
    assert s.undo("m").parts.keys() == set()
    with pytest.raises(ModelError):
        s.undo("m")
    assert s.redo("m").parts.keys() == {"a"}
    _edit(s, "m", "c")  # new edit drops redo
    with pytest.raises(ModelError):
        s.redo("m")


def test_history_cap(tmp_path):
    s = ModelStore(tmp_path)
    s.create("m")
    for i in range(MAX_HISTORY + 10):
        _edit(s, "m", f"p{i}")
    assert s.history("m")[0] == MAX_HISTORY


def test_named_snapshot_restore(tmp_path):
    s = ModelStore(tmp_path)
    s.create("m")
    _edit(s, "m", "a")
    s.snapshot("m", "v1")
    _edit(s, "m", "b")
    assert s.restore("m", "v1").parts.keys() == {"a"}
    assert s.undo("m").parts.keys() == {"a", "b"}
    with pytest.raises(ModelError):
        s.restore("m", "nope")


def test_corrupt_model_file_is_a_model_error(tmp_path):
    store = ModelStore(tmp_path)
    store.create("board")
    store._path("board").write_text("{not json", encoding="utf-8")
    with pytest.raises(ModelError, match="cannot read model"):
        store.load("board")
