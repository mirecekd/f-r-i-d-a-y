# backend/tests/test_files_tools.py
"""file_upload protocol, file_card schema, download route and the read/list/summarize tools (model faked)."""

import asyncio
import base64

import pytest
from fastapi.testclient import TestClient

from app import main
from app.files import card, store, tools
from app.views import VIEW_KINDS
from tests.file_helpers import csv_cp1250, docx_bytes, pdf_bytes
from tests.test_agent_ws import drain
from tests.vision_helpers import png_bytes


@pytest.fixture
def client():
    return TestClient(main.app)


def run(coro):
    return asyncio.run(coro)


def upload(name: str, raw: bytes, t: str = "file_upload") -> dict:
    return {"t": t, "id": "c1", "name": name, "mime": "application/octet-stream", "data_b64": base64.b64encode(raw).decode()}


def drop_via_ws(client, name, raw):
    """Upload, wait for the entity op, then open the card with entity_open; returns (messages before the open, card)."""
    with client.websocket_connect("/ws") as ws:
        drain(ws, lambda m: m["t"] == "models")
        ws.send_json(upload(name, raw))
        seen = drain(ws, lambda m: m["t"] == "scene")
        ws.send_json({"t": "entity_open", "id": seen[-1]["ops"][0]["obj"]["id"]})
        return seen, drain(ws, lambda m: m["t"] == "view")[-1]


def test_file_upload_places_the_entity_after_file_ready_and_opens_the_card_on_demand(client):
    seen, view = drop_via_ws(client, "lidi.csv", csv_cp1250())
    ready, scene = seen[-2], seen[-1]
    assert ready["t"] == "file_ready" and ready["client_id"] == "c1" and ready["kind"] == "csv" and ready["size"] > 0
    assert not [m for m in seen if m["t"] == "view"]  # no card pops up on drop
    obj = scene["ops"][0]["obj"]
    assert obj["id"] == f"ent-file-{ready['id'][:8]}" and obj["ref"] == {"type": "file", "id": ready["id"]} and obj["pos"]
    assert ready["url"] == f"/api/files/{ready['id']}" and view["kind"] == "file_card" and view["title"] == "lidi.csv"
    d = view["data"]
    assert {"id", "name", "kind", "size", "title", "summary", "meta", "outline", "text_excerpt", "truncated", "download_url"} <= set(d)
    assert d["tables"][0]["columns"] == ["jmeno", "mesto"] and d["download_url"] == ready["url"]
    assert "file_card" in VIEW_KINDS


def test_pdf_card_has_page_meta(client):
    d = drop_via_ws(client, "a.pdf", pdf_bytes(2))[1]["data"]
    assert d["kind"] == "pdf" and d["meta"]["pages"] == 2 and "Hello Friday" in d["text_excerpt"]


def test_image_through_file_upload_takes_the_vision_path(client):
    with client.websocket_connect("/ws") as ws:
        drain(ws, lambda m: m["t"] == "models")
        ws.send_json({**upload("p.png", png_bytes()), "mime": "image/png", "analyze": False})
        assert drain(ws, lambda m: m["t"] in ("image_ready", "file_ready"))[-1]["t"] == "image_ready"


def test_bad_base64_and_oversize_give_errors(client):
    with client.websocket_connect("/ws") as ws:
        drain(ws, lambda m: m["t"] == "models")
        ws.send_json({"t": "file_upload", "id": "z", "name": "x", "mime": "", "data_b64": "!!!"})
        err = drain(ws, lambda m: m["t"] == "error")[-1]
        assert "base64" in err["message"] and err["id"] == "z"
        ws.send_json({"t": "file_upload", "name": "x", "mime": "", "data_b64": "A" * 40_000_000})
        assert "25 MB" in drain(ws, lambda m: m["t"] == "error")[-1]["message"]


def test_http_upload_and_download_is_an_attachment(client):
    body = client.post("/api/upload", files={"file": ("../evil name.docx", docx_bytes(), "text/html")}).json()
    assert body["kind"] == "docx" and body["name"] == "..evil name.docx"
    got = client.get(body["url"])
    assert got.content == docx_bytes() and got.headers["content-disposition"].startswith("attachment")
    assert got.headers["x-content-type-options"] == "nosniff" and got.headers["content-type"] == "application/octet-stream"
    assert client.get("/api/files/../../etc/passwd").status_code in (404, 422)
    assert client.get("/api/files/" + "0" * 32).status_code == 404
    assert client.post("/api/upload", files={"file": ("x.bin", b"a" * (26 * 1024 * 1024))}).status_code == 413


def test_http_upload_announces_and_places_the_file_on_every_open_connection(client):
    with client.websocket_connect("/ws") as ws:
        drain(ws, lambda m: m["t"] == "models")
        body = client.post("/api/upload", files={"file": ("n.docx", docx_bytes(), "text/html")}).json()
        seen = drain(ws, lambda m: m["t"] == "scene")
    ready = next(m for m in seen if m["t"] == "file_ready")
    assert ready["id"] == body["id"] and seen.index(ready) < len(seen) - 1
    assert seen[-1]["ops"][0]["obj"]["ref"] == {"type": "file", "id": body["id"]}


@pytest.fixture
def stored(tmp_path):
    from app.files.extract import extract

    raw = ("line one\n" + "word " * 9000).encode()
    return store.save(raw, "big.txt", extract(raw, "big.txt"))


def registry_for(monkeypatch, replies=None):
    from app.scene import SceneStore
    from app.tools_friday.ctx import Ctx
    from app.vision.service import VisionService
    from app.voice.tools import ToolRegistry

    sent: list = []

    async def emit(m):
        sent.append(m)

    async def fake_chat(model, messages, tool_defs, on_delta=None):
        (replies if replies is not None else []).append(messages[0]["content"])
        return {"text": "x" * 900, "tool_calls": []}

    monkeypatch.setattr(tools, "chat", fake_chat)
    ctx = Ctx(SceneStore(), emit)
    reg = ToolRegistry()
    tools.register_file_tools(reg, ctx, VisionService(ctx, lambda: "m"), lambda: "m")
    return reg, sent


def test_read_file_pages_and_delimits(stored, monkeypatch):
    reg, _ = registry_for(monkeypatch)
    first = run(reg.tools["read_file"].handler({"file_id": stored["id"][:10]}))
    assert first["part"] == 1 and first["parts"] == 3 and first["content"].startswith("<file-content")
    assert first["content"].endswith("</file-content>") and "untrusted" in first["untrusted"]
    assert len(first["content"]) < tools.PAGE_CHARS + 200
    assert run(reg.tools["read_file"].handler({"file_id": stored["id"], "part": 3}))["part"] == 3
    assert "does not exist" in run(reg.tools["read_file"].handler({"file_id": stored["id"], "part": 9}))["error"]
    assert "unknown" in run(reg.tools["read_file"].handler({"file_id": "nope"}))["error"]


def test_list_file_to_scene_and_summarize(stored, monkeypatch):
    seen: list = []
    reg, sent = registry_for(monkeypatch, seen)
    assert run(reg.tools["list_files"].handler({}))["files"][0]["file_id"] == stored["id"]
    assert run(reg.tools["file_to_scene"].handler({"file_id": stored["id"]}))["ok"]
    assert sent[-1]["t"] == "scene" and sent[-1]["ops"][0]["obj"]["kind"] == "entity"  # no 2D card until double-click
    s = run(reg.tools["summarize_file"].handler({"file_id": stored["id"]}))
    assert len(s["summary"]) == tools.SUMMARY_CHARS and s["input_truncated"]
    assert len(seen[0]) < tools.SUMMARY_INPUT + 600 and "untrusted" in seen[0]


def test_card_excerpt_is_capped_and_marked_truncated(stored):
    d = card.card_data(stored, store.text_of(stored["id"]))
    assert len(d["text_excerpt"]) == card.EXCERPT_CHARS and d["truncated"]


def test_voice_hint_is_sent_without_a_reply(monkeypatch):
    from app.files.service import FileService, attach_hint
    from app.scene import SceneStore
    from app.tools_friday.ctx import Ctx
    from app.vision.service import VisionService

    async def emit(m):
        pass

    hints: list[str] = []

    async def hint(t):
        hints.append(t)

    ctx = Ctx(SceneStore(), emit)
    run(FileService(ctx, VisionService(ctx, lambda: "m")).on_upload(upload("a.pdf", pdf_bytes(2)), hint))
    assert hints[0].startswith("User attached a.pdf (pdf, 2 pages); use read_file") and hints[0] == attach_hint(
        {"name": "a.pdf", "kind": "pdf", "meta": {"pages": 2}, "id": hints[0].split("file_id ")[1][:-1]})
