# backend/tests/test_views.py
import pytest
from fastapi.testclient import TestClient

from app.views import MAX_PAYLOAD_BYTES, ViewError, view_close_msg, view_msg
from app.views_demo import sample_views


def test_view_msg_shape():
    m = view_msg("markdown", {"text": "hi"}, "T", "abc")
    assert m == {"t": "view", "id": "abc", "kind": "markdown", "data": {"text": "hi"}, "title": "T"}


def test_view_msg_rejects_unknown_kind_and_big_payload():
    with pytest.raises(ViewError):
        view_msg("video", {})
    with pytest.raises(ViewError):
        view_msg("code", {"code": "x" * (MAX_PAYLOAD_BYTES + 1)})


def test_view_close():
    assert view_close_msg("a") == {"t": "view_close", "id": "a"}


def test_demo_covers_all_kinds():
    assert {v["kind"] for v in sample_views()} == {"image", "chart", "table", "markdown", "code", "diagram", "map", "json"}


def _demo_frames(client: TestClient) -> list[dict]:
    with client.websocket_connect("/ws") as ws:
        for _ in range(4):
            ws.receive_json()
        ws.send_json({"t": "demo", "what": "views"})
        return [ws.receive_json() for _ in range(len(sample_views()))]


def test_demo_ws_guarded_by_env(monkeypatch):
    from app.main import app

    monkeypatch.setenv("FRIDAY_DEMO", "1")
    assert all(f["t"] == "view" for f in _demo_frames(TestClient(app)))
    monkeypatch.delenv("FRIDAY_DEMO")
    with TestClient(app).websocket_connect("/ws") as ws:
        for _ in range(4):
            ws.receive_json()
        ws.send_json({"t": "demo", "what": "views"})
        assert ws.receive_json()["t"] == "error"
