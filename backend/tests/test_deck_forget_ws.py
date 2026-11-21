# backend/tests/test_deck_forget_ws.py
"""The deck window's 'Zapomenout' button sends {t:'deck_forget'}: the registry row goes, the stored item stays."""

from fastapi.testclient import TestClient

from app import deck, main


def drain(ws, until):
    seen = []
    while True:
        msg = ws.receive_json()
        seen.append(msg)
        if until(msg):
            return seen


def test_forget_message_removes_the_deck_row_but_not_the_stored_item(tmp_path, monkeypatch):
    monkeypatch.setenv("FRIDAY_DATA_DIR", str(tmp_path))
    stored = tmp_path / "keep-me.txt"
    stored.write_text("still here", encoding="utf-8")
    deck_id = deck.register("note", "forget-test-1", "Forget me", source="upload")
    assert deck.get(deck_id) is not None

    with TestClient(main.app).websocket_connect("/ws") as ws:
        drain(ws, lambda m: m["t"] == "models")
        ws.send_json({"t": "deck_forget", "id": deck_id})
        seen = drain(ws, lambda m: m == {"t": "deck_changed", "id": deck_id})
        assert {"t": "deck_changed", "id": deck_id} in seen
        ws.send_json({"t": "deck_list"})
        listing = drain(ws, lambda m: m["t"] == "deck")[-1]
        assert deck_id not in [it["id"] for it in listing["items"]]

    assert deck.get(deck_id) is None
    assert stored.read_text(encoding="utf-8") == "still here"  # nothing outside the registry was touched


def test_forget_unknown_id_is_a_readable_error(tmp_path, monkeypatch):
    monkeypatch.setenv("FRIDAY_DATA_DIR", str(tmp_path))
    with TestClient(main.app).websocket_connect("/ws") as ws:
        drain(ws, lambda m: m["t"] == "models")
        ws.send_json({"t": "deck_forget", "id": "does-not-exist"})
        err = drain(ws, lambda m: m["t"] == "error")[-1]
        assert "unknown item" in err["message"]
