# backend/tests/test_demo_ws.py
import pytest
from fastapi.testclient import TestClient

from app import main
from app.scene import SceneStore
from app.scene_demo import demo_objects
from app.scene_schema import KIND_PROPS


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "scene", SceneStore())
    return TestClient(main.app)


def drain_hello(ws) -> None:
    for _ in range(4):
        ws.receive_json()


def test_demo_objects_are_valid_and_cover_every_kind():
    store = SceneStore()
    store.apply([{"op": "add", "obj": o} for o in demo_objects()])
    assert {o["kind"] for o in store.objects()} == set(KIND_PROPS)


def test_demo_message_guarded_by_env(client, monkeypatch):
    monkeypatch.delenv("FRIDAY_DEMO", raising=False)
    with client.websocket_connect("/ws") as ws:
        drain_hello(ws)
        ws.send_json({"t": "demo", "what": "scene"})
        assert ws.receive_json()["t"] == "error"


def test_demo_message_sends_scene_full(client, monkeypatch):
    monkeypatch.setenv("FRIDAY_DEMO", "1")
    with client.websocket_connect("/ws") as ws:
        drain_hello(ws)
        ws.send_json({"t": "demo", "what": "scene"})
        msg = ws.receive_json()
        assert msg["t"] == "scene_full" and len(msg["objects"]) == len(demo_objects())
        assert ws.receive_json()["ops"][0]["op"] == "camera"


def test_select_message_updates_store(client, monkeypatch):
    monkeypatch.setenv("FRIDAY_DEMO", "1")
    with client.websocket_connect("/ws") as ws:
        drain_hello(ws)
        ws.send_json({"t": "demo", "what": "scene"})
        ws.receive_json()
        ws.receive_json()
        ws.send_json({"t": "select", "ids": ["robot", "nope"]})
        ws.send_json({"t": "ping"})
        assert ws.receive_json()["t"] == "pong"
        assert main.scene.selected == ["robot"]
