# backend/tests/test_assets_tools.py
"""asset_find / asset_place / asset_credits, the `assets_credits` message and the model route (no network)."""

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import main
from app.assets import fetch, index
from app.assets.tools import register_asset_tools
from app.scene import SceneStore
from app.tools_friday.ctx import Ctx
from app.voice.tools import ToolRegistry
from app.webpages.urlguard import UrlRefused

GLB = b"glTF" + b"\x02\x00\x00\x00" + b"x" * 32


class Rig:
    def __init__(self, monkeypatch, fail: bool = False) -> None:
        self.sent: list[dict[str, Any]] = []
        self.ctx = Ctx(SceneStore(), self._emit)
        self.registry = ToolRegistry()
        self.session = register_asset_tools(self.registry, self.ctx)
        self.downloads: list[str] = []

        async def fake_ensure(asset, **_):
            if fail:
                raise UrlRefused("the model server answered HTTP 500")
            self.downloads.append(asset.id)
            index.file_of(asset.id).parent.mkdir(parents=True, exist_ok=True)
            index.file_of(asset.id).write_bytes(GLB)
            return True

        monkeypatch.setattr(fetch, "ensure", fake_ensure)

    async def _emit(self, msg: dict[str, Any]) -> None:
        self.sent.append(msg)

    def call(self, name: str, **args: Any) -> dict[str, Any]:
        return asyncio.run(self.registry.tools[name].handler(args))


def test_find_returns_ids_and_validates_input(monkeypatch):
    rig = Rig(monkeypatch)
    out = rig.call("asset_find", query="zidle", limit=3)
    assert out["ok"] and 1 <= len(out["results"]) <= 3
    assert all(index.get(r["id"]) for r in out["results"])
    assert rig.call("asset_find", query="")["error"]
    assert rig.call("asset_find", query="qqqzzz")["results"] == []
    assert rig.call("asset_find", query="chair", limit="many")["error"]


def test_place_adds_a_labelled_gltf_object_and_returns_credit(monkeypatch):
    rig = Rig(monkeypatch)
    asset_id = rig.call("asset_find", query="chair")["results"][0]["id"]
    out = rig.call("asset_place", id=asset_id, pos=[1, 0, 2], fit=1.5, label="Moje zidle")
    assert out["ok"] and out["downloaded"] and "CC0-1.0" in out["credit"] and "Quaternius" in out["credit"]
    obj = next(o for o in rig.ctx.scene.objects() if o["id"] == out["object_id"])
    assert obj["kind"] == "gltf" and obj["url"] == f"/asset-models/{asset_id}.glb" and obj["fit"] == 1.5
    assert obj["pos"] == [1.0, 0.0, 2.0] and obj["label"] == "Moje zidle"
    assert rig.sent[0]["t"] == "scene" and rig.sent[-1] == {"t": "assets", "items": rig.session.credits()}
    again = rig.call("asset_place", id=asset_id)  # a second copy gets its own object id
    assert again["object_id"] != out["object_id"] and len(rig.ctx.scene.objects()) == 2


@pytest.mark.parametrize("args", [
    {"id": "nope"}, {"id": "../etc/passwd"}, {"id": None},
])
def test_place_unknown_id_is_an_error_and_scene_unchanged(monkeypatch, args):
    rig = Rig(monkeypatch)
    assert "unknown asset id" in rig.call("asset_place", **args)["error"]
    assert rig.ctx.scene.objects() == [] and rig.downloads == []


@pytest.mark.parametrize("bad", [{"pos": [1, 2]}, {"pos": "x"}, {"fit": 0}, {"fit": -1}, {"fit": 1e6}, {"fit": "big"}, {"label": 5}])
def test_place_bad_arguments(monkeypatch, bad):
    rig = Rig(monkeypatch)
    asset_id = next(iter(index.load_index()))
    assert "error" in rig.call("asset_place", id=asset_id, **bad)
    assert rig.ctx.scene.objects() == [] and rig.downloads == []


def test_place_reports_a_failed_download(monkeypatch):
    rig = Rig(monkeypatch, fail=True)
    out = rig.call("asset_place", id=next(iter(index.load_index())))
    assert "cannot get the model" in out["error"] and rig.ctx.scene.objects() == [] and rig.session.credits() == []


def test_credits_tool_and_message_list_only_placed_models(monkeypatch):
    rig = Rig(monkeypatch)
    assert rig.call("asset_credits")["credits"] == []
    asset = index.load_index()[rig.call("asset_find", query="tree")["results"][0]["id"]]
    rig.call("asset_place", id=asset.id)
    assert rig.call("asset_credits")["credits"] == [asset.credit()]
    rig.sent.clear()
    asyncio.run(rig.session.on_message({"t": "assets_credits"}))
    assert rig.sent == [{"t": "assets", "items": [asset.public()]}]
    assert set(asset.public()) == {"name", "author", "license", "source_page"}


@pytest.fixture
def client():
    return TestClient(main.app)


def test_route_serves_a_cached_model(client):
    asset_id = next(iter(index.load_index()))
    assert client.get(f"/asset-models/{asset_id}.glb").status_code == 404  # not downloaded yet
    index.file_of(asset_id).parent.mkdir(parents=True, exist_ok=True)
    index.file_of(asset_id).write_bytes(GLB)
    res = client.get(f"/asset-models/{asset_id}.glb")
    assert res.status_code == 200 and res.content == GLB and res.headers["content-type"] == "model/gltf-binary"


@pytest.mark.parametrize("name", [
    "../deck.db", "..%2Fdeck.db", "%2e%2e%2fdeck.db", "..%5Cdeck.db", "%2Fetc%2Fpasswd", "/etc/passwd", "....//x.glb",
    "unknown-model.glb", "QHOME-CHAIR-1.glb", "x.glb%00", "x.glb.", "x", ".glb", "a%2F..%2F..%2Fb.glb",
])
def test_route_refuses_traversal_and_unknown_names(client, name):
    index.assets_dir().mkdir(parents=True, exist_ok=True)
    (index.assets_dir().parent / "deck.db").write_bytes(b"secret")
    res = client.get(f"/asset-models/{name}")
    assert res.status_code in (404, 400) and b"secret" not in res.content


def test_route_refuses_valid_id_with_other_extension(client):
    asset_id = next(iter(index.load_index()))
    index.file_of(asset_id).parent.mkdir(parents=True, exist_ok=True)
    index.file_of(asset_id).write_bytes(GLB)
    assert client.get(f"/asset-models/{asset_id}.gltf").status_code == 404
    assert client.get(f"/asset-models/{asset_id}").status_code == 404


def test_ws_assets_credits_message_answers_with_assets(client):
    with client.websocket_connect("/ws") as ws:
        for _ in range(3):
            ws.receive_json()
        ws.send_json({"t": "assets_credits"})
        seen = []
        for _ in range(12):
            seen.append(ws.receive_json())
            if seen[-1]["t"] == "assets":
                break
        assert seen[-1] == {"t": "assets", "items": []}
