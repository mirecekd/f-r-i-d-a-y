# backend/tests/test_model3d_proposals.py
import pytest

from app.model3d.compile import compile_model
from app.model3d.model import Model, ModelError
from app.model3d.proposals import ProposalBook
from app.model3d.store import ModelStore
from app.scene import SceneStore

CHANGES = [
    {"op": "add", "part": {"id": "new", "kind": "box", "pos": [5, 0, 0]}},
    {"op": "edit", "id": "a", "props": {"pos": [9, 0, 0], "props": {"net": "VCC"}}},
    {"op": "remove", "id": "b"},
]


def _setup(tmp_path):
    store = ModelStore(tmp_path)
    store.create("m")
    m = Model.from_dict({"id": "m", "parts": [{"id": "a", "kind": "box"}, {"id": "b", "kind": "box"}]})
    store.commit(store.load("m"), m)
    scene = SceneStore()
    scene.apply(compile_model(m))
    return store, m, scene


def test_propose_leaves_model_untouched_and_adds_ghosts(tmp_path):
    store, m, scene = _setup(tmp_path)
    before = m.to_dict()
    prop = ProposalBook().propose(m, CHANGES)
    assert m.to_dict() == before and store.load("m").to_dict() == before
    scene.apply(prop.ghost_ops)
    ids = {o["id"]: o for o in scene.objects()}
    assert {"ghost:p1:new", "ghost:p1:a", "ghost:p1:b"} <= set(ids)
    assert ids["ghost:p1:new"]["opacity"] < 1 and ids["m:m:a"]["pos"] == [0.0, 0.0, 0.0]
    assert "+ add new" in prop.summary and "~ edit a" in prop.summary and "- remove b" in prop.summary


def test_accept_applies_with_snapshot_and_removes_ghost(tmp_path):
    store, m, scene = _setup(tmp_path)
    book = ProposalBook()
    prop = book.propose(m, CHANGES)
    scene.apply(prop.ghost_ops)
    after, removal = book.accept(prop.id, store)
    scene.apply(removal)
    assert not [o for o in scene.objects() if o["id"].startswith("ghost:")]
    assert set(store.load("m").parts) == {"a", "new"}
    assert after.parts["a"].props == {"net": "VCC"}
    assert set(store.undo("m").parts) == {"a", "b"}
    with pytest.raises(ModelError):
        book.accept(prop.id, store)


def test_reject_removes_ghost_only(tmp_path):
    store, m, scene = _setup(tmp_path)
    book = ProposalBook()
    prop = book.propose(m, CHANGES)
    scene.apply(prop.ghost_ops)
    scene.apply(book.reject(prop.id))
    assert not [o for o in scene.objects() if o["id"].startswith("ghost:")]
    assert set(store.load("m").parts) == {"a", "b"}
    with pytest.raises(ModelError):
        book.reject(prop.id)


def test_invalid_changes_rejected(tmp_path):
    _, m, _ = _setup(tmp_path)
    with pytest.raises(ModelError):
        ProposalBook().propose(m, [{"op": "edit", "id": "zzz", "props": {}}])
    with pytest.raises(ModelError):
        ProposalBook().propose(m, [{"op": "add", "part": {"id": "a"}}])
