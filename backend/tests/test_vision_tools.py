# backend/tests/test_vision_tools.py
"""WebSocket image_upload flow and the analyze_image / list_images / show_in_scene tools (model mocked)."""

import asyncio
import base64

import pytest
from fastapi.testclient import TestClient

from app import agent_wiring, main
from app.agent import agent_model
from app.vision import analyze, service
from tests.test_agent_ws import drain
from tests.vision_helpers import jpeg_with_gps, png_bytes

ANALYSIS = {"kind": "photo", "summary": "A brown rectangle.", "people_count": 0, "objects": [], "text_found": [],
            "scene": None, "location_hint": None, "rooms": [], "dimensions_hint": None, "confidence": 0.9, "notes": "n"}


@pytest.fixture
def client(monkeypatch):
    calls = []

    async def fake_analyze(jpeg, exif, pinned):
        calls.append((len(jpeg), exif, pinned))
        return "fake-vision", dict(ANALYSIS)

    monkeypatch.setattr(service, "analyze_picture", fake_analyze)
    monkeypatch.setattr(analyze, "analyze_picture", fake_analyze)
    c = TestClient(main.app)
    c.calls = calls  # type: ignore[attr-defined]
    return c


def upload_msg(raw: bytes, mime: str, **extra) -> dict:
    return {"t": "image_upload", "id": "c1", "name": "p.jpg", "mime": mime, "data_b64": base64.b64encode(raw).decode(), **extra}


def test_upload_emits_ready_then_entity_and_the_card_only_on_open(client):
    with client.websocket_connect("/ws") as ws:
        drain(ws, lambda m: m["t"] == "models")
        ws.send_json(upload_msg(jpeg_with_gps(), "image/jpeg"))
        seen = drain(ws, lambda m: m["t"] == "notice")
        ready = next(m for m in seen if m["t"] == "image_ready")
        scene = next(m for m in seen if m["t"] == "scene")
        assert ready["client_id"] == "c1" and ready["url"] == f"/api/uploads/{ready['id']}.jpg" and ready["exif"]["lat"]
        assert scene["ops"][0]["obj"]["ref"] == {"type": "image", "id": ready["id"]}
        assert seen.index(ready) < seen.index(scene) and not [m for m in seen if m["t"] == "view"]
        ws.send_json({"t": "entity_open", "id": scene["ops"][0]["obj"]["id"]})
        card = drain(ws, lambda m: m["t"] == "view")[-1]
    assert card["kind"] == "image_card" and card["data"]["url"] == ready["url"]
    assert card["data"]["summary"] == "A brown rectangle." and card["data"]["exif"]["camera_make"] == "FriCam"
    assert len(client.calls) == 1  # the cached analysis made opening instant
    assert client.calls[0][2] == agent_model.DEFAULT_MODEL and "lat" in client.calls[0][1]


def test_upload_with_analyze_false_skips_the_model(client):
    with client.websocket_connect("/ws") as ws:
        drain(ws, lambda m: m["t"] == "models")
        ws.send_json(upload_msg(png_bytes(), "image/png", analyze=False))
        drain(ws, lambda m: m["t"] == "image_ready")
        ws.send_json({"t": "ping"})
        assert drain(ws, lambda m: m["t"] == "pong")[-1]["t"] == "pong"
    assert client.calls == []


@pytest.mark.parametrize("raw,mime,text", [
    (b"<html>", "image/png", "not a jpeg"),
    (png_bytes(), "text/html", "not allowed"),
])
def test_bad_upload_gives_error_and_no_image_ready(client, raw, mime, text):
    with client.websocket_connect("/ws") as ws:
        drain(ws, lambda m: m["t"] == "models")
        ws.send_json(upload_msg(raw, mime))
        err = drain(ws, lambda m: m["t"] == "error")[-1]
    assert text in err["message"] and err["id"] == "c1"


def test_invalid_base64_and_oversize_payload_are_rejected(client):
    with client.websocket_connect("/ws") as ws:
        drain(ws, lambda m: m["t"] == "models")
        ws.send_json({"t": "image_upload", "name": "x", "mime": "image/png", "data_b64": "!!!"})
        assert "base64" in drain(ws, lambda m: m["t"] == "error")[-1]["message"]
        ws.send_json({"t": "image_upload", "name": "x", "mime": "image/png", "data_b64": "A" * (service.MAX_B64_CHARS + 1)})
        assert "12 MB" in drain(ws, lambda m: m["t"] == "error")[-1]["message"]


def test_image_to_scene_message_adds_the_scene_object(client):
    with client.websocket_connect("/ws") as ws:
        drain(ws, lambda m: m["t"] == "models")
        ws.send_json(upload_msg(png_bytes((400, 200)), "image/png", analyze=False))
        image_id = drain(ws, lambda m: m["t"] == "image_ready")[-1]["id"]
        ws.send_json({"t": "image_to_scene", "id": image_id})
        op = drain(ws, lambda m: m["t"] == "scene")[-1]["ops"][0]
        assert op["op"] == "add" and op["obj"]["id"] == f"ent-image-{image_id[:8]}" and op["obj"]["kind"] == "entity"
        assert op["obj"]["thumb"] == f"/api/uploads/{image_id}.png" and op["obj"]["ref"] == {"type": "image", "id": image_id}
        ws.send_json({"t": "image_to_scene", "id": "zz"})
        assert "unknown image_id" in drain(ws, lambda m: m["t"] == "error")[-1]["message"]


def test_tools_list_analyze_and_show_in_scene(client):
    asyncio.run(tools_scenario(client))


async def tools_scenario(client):
    sent = []

    async def emit(msg):
        sent.append(msg)

    session = agent_wiring.AgentSession(main.scene, emit, main.tool_registry)
    await session.vision.on_upload(upload_msg(png_bytes((400, 200)), "image/png", analyze=False))
    image_id = next(m for m in sent if m["t"] == "image_ready")["id"]  # deck_changed may arrive first
    tools = session.registry.tools
    assert tools["analyze_image"].long and tools["analyze_image"].scheduling == "WHEN_IDLE"

    listed = await tools["list_images"].handler({})
    assert listed["images"][0]["image_id"] == image_id and listed["images"][0]["analysed"] is False

    result = await tools["analyze_image"].handler({"image_id": image_id[:8]})
    assert result["ok"] and result["analysis"]["summary"] == "A brown rectangle." and result["analysis"]["model"] == "fake-vision"
    assert sum(1 for m in sent if m["t"] == "view") == 1
    await tools["analyze_image"].handler({"image_id": image_id})  # cached: no second model call, no second card
    assert len(client.calls) == 1 and sum(1 for m in sent if m["t"] == "view") == 1
    assert (await tools["list_images"].handler({}))["images"][0]["kind"] == "photo"

    shown = await tools["show_in_scene"].handler({"image_id": image_id, "pos": [1, 2, 3], "scale": 2})
    assert shown == {"ok": True, "object_id": f"ent-image-{image_id[:8]}", "pos": [1, 2, 3]}
    obj = next(o for o in main.scene.objects() if o["id"] == shown["object_id"])
    assert obj["kind"] == "entity" and obj["thumb"] == f"/api/uploads/{image_id}.png" and obj["pos"] == [1, 2, 3]
    assert sent[-1]["t"] == "scene"
    assert "error" in await tools["show_in_scene"].handler({"image_id": "zz"})
    assert "error" in await tools["analyze_image"].handler({"image_id": "../prefs"})
    await session.close()
