# backend/tests/test_workshop_store.py
"""Workshop store: disk round trip, atomic write, origin allocation, damaged files."""

import json
import os

import pytest

from app.workshop import store


def test_create_roundtrip_and_id_shape():
    rec = store.create("Zidle")
    assert store.valid_id(rec["id"]) and len(rec["id"]) == 12
    again = store.load(rec["id"])
    assert again["title"] == "Zidle" and again["spec"] is None and again["origin_n"] == 1
    assert again["history"] == [] and again["redo"] == []
    assert (store.workshops_dir() / f"{rec['id']}.json").is_file()


def test_empty_title_gets_the_default():
    assert store.create("  ")["title"] == store.DEFAULT_TITLE


def test_origin_is_the_lowest_free_slot_and_stable():
    a, b = store.create("a"), store.create("b")
    assert (a["origin_n"], b["origin_n"]) == (1, 2)
    assert store.origin_of(b["origin_n"]) == (0.0, 0.0, 800.0)
    store.delete(a["id"])
    c = store.create("c")
    assert c["origin_n"] == 1  # the freed slot is reused
    assert store.load(b["id"])["origin_n"] == 2  # the others never move


def test_history_is_capped_at_fifty(monkeypatch):
    rec = store.create("h")
    rec["history"] = [{"parts": [], "name": str(i)} for i in range(80)]
    store.save(rec)
    kept = store.load(rec["id"])["history"]
    assert len(kept) == 50 and kept[-1]["name"] == "79"


def test_failed_write_keeps_the_old_file(monkeypatch):
    rec = store.create("keep")
    path = store.workshops_dir() / f"{rec['id']}.json"
    before = path.read_text(encoding="utf-8")

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    rec["title"] = "changed"
    with pytest.raises(OSError):
        store.save(rec)
    assert path.read_text(encoding="utf-8") == before


def test_bad_and_unknown_ids_are_clear_errors():
    for bad in ("../etc/passwd", "short", "g" * 12, None):
        with pytest.raises(store.WorkshopError):
            store.load(bad)  # type: ignore[arg-type]
    with pytest.raises(store.WorkshopError, match="unknown workshop"):
        store.load("0" * 12)


def test_damaged_file_is_an_error_and_does_not_break_origin_allocation():
    rec = store.create("x")
    (store.workshops_dir() / f"{rec['id']}.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(store.WorkshopError, match="cannot read"):
        store.load(rec["id"])
    assert store.create("y")["origin_n"] == 1  # the damaged file is skipped


def test_file_with_a_foreign_id_is_refused():
    rec = store.create("x")
    path = store.workshops_dir() / f"{rec['id']}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["id"] = "1" * 12
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(store.WorkshopError, match="damaged"):
        store.load(rec["id"])
