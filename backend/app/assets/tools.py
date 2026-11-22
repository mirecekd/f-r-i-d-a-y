# backend/app/assets/tools.py
"""Model tools asset_find, asset_place, asset_credits and the `assets_credits` WebSocket message."""

import re
from typing import Any

from app.assets import fetch, index, search
from app.assets.index import Asset
from app.tools_friday.ctx import Ctx
from app.scene import SceneError
from app.voice.tools import Tool, ToolRegistry
from app.webpages.urlguard import UrlRefused

MAX_FIT = 100.0
DEFAULT_FIT = 1.0
_VEC3 = {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}


def model_url(asset: Asset) -> str:
    return f"/asset-models/{asset.id}.glb"


def _brief(asset: Asset) -> dict[str, Any]:
    return {"id": asset.id, "name": asset.name, "category": asset.category, "pack": asset.pack, "tags": list(asset.tags)[:8]}


class AssetSession:
    """Per connection: the models placed so far (for the credits list)."""

    def __init__(self, ctx: Ctx) -> None:
        self.ctx = ctx
        self.placed: dict[str, Asset] = {}

    def credits(self) -> list[dict[str, str]]:
        return [a.public() for a in self.placed.values()]

    async def send_credits(self) -> None:
        await self.ctx.emit({"t": "assets", "items": self.credits()})

    async def on_message(self, msg: dict[str, Any]) -> None:
        if msg.get("t") == "assets_credits":
            await self.send_credits()

    async def find(self, a: dict[str, Any]) -> dict[str, Any]:
        query = a.get("query")
        category = a.get("category")
        if not isinstance(query, str) or not query.strip():
            return {"error": "query must be a non-empty string"}
        try:
            limit = int(a.get("limit") or search.MAX_LIMIT)
        except (TypeError, ValueError):
            return {"error": "limit must be a number"}
        hits = search.find(query, category if isinstance(category, str) else None, limit)
        if not hits:
            return {"ok": True, "results": [], "hint": "nothing found; try another word or a broader category"}
        return {"ok": True, "results": [_brief(h) for h in hits]}

    async def place(self, a: dict[str, Any]) -> dict[str, Any]:
        asset = index.get(a.get("id"))
        if asset is None:
            return {"error": "unknown asset id; call asset_find first and use an id from its results"}
        pos, fit, label = a.get("pos"), a.get("fit", DEFAULT_FIT), a.get("label")
        if pos is not None and not (isinstance(pos, list) and len(pos) == 3 and all(_num(x) for x in pos)):
            return {"error": "pos must be [x, y, z] numbers"}
        if not _num(fit) or not 0 < float(fit) <= MAX_FIT:
            return {"error": f"fit must be a number above 0 and at most {MAX_FIT:g} (the longest side of the model in scene units)"}
        if label is not None and not isinstance(label, str):
            return {"error": "label must be a string"}
        try:
            downloaded = await fetch.ensure(asset)
        except UrlRefused as e:
            return {"error": f"cannot get the model: {e}"}
        obj: dict[str, Any] = {"id": self._object_id(asset), "kind": "gltf", "url": model_url(asset), "fit": float(fit),
                               "label": (label or asset.name)[:200]}
        if pos is not None:
            obj["pos"] = [float(x) for x in pos]
        ops = [{"op": "add", "obj": obj}]
        try:
            self.ctx.scene.apply(ops)
        except SceneError as e:
            return {"error": str(e)}
        await self.ctx.emit({"t": "scene", "ops": ops})
        self.placed[asset.id] = asset
        await self.send_credits()
        return {"ok": True, "object_id": obj["id"], "downloaded": downloaded, "credit": asset.credit()}

    def _object_id(self, asset: Asset) -> str:
        taken = {o["id"] for o in self.ctx.scene.objects()}
        base = re.sub(r"[^a-z0-9-]+", "-", asset.id)
        n = 1
        while f"{base}-{n}" in taken:
            n += 1
        return f"{base}-{n}"

    async def credits_tool(self, a: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "credits": [x.credit() for x in self.placed.values()]}


def _num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) < 1e9


def register_asset_tools(registry: ToolRegistry, ctx: Ctx) -> AssetSession:
    """Add the asset tools to this connection's registry; returns the session that answers `assets_credits`."""
    session = AssetSession(ctx)
    registry.register(Tool(
        "asset_find",
        "Search the built-in catalog of ready-made free (CC0) 3D models: furniture, appliances, plants, trees, rocks, "
        "animals, people, vehicles, buildings, street items, props. Works with Czech or English words. Returns ids for "
        "asset_place. Use when the user wants a recognisable real-world object instead of a shape built from primitives.",
        {"type": "object", "properties": {
            "query": {"type": "string", "description": "what to look for, e.g. 'chair', 'zidle', 'pine tree'"},
            "category": {"type": "string", "description": "optional: furniture, nature, props, buildings, city, vehicles, animals, characters"},
            "limit": {"type": "integer", "description": "at most 8"}}, "required": ["query"]},
        session.find))
    registry.register(Tool(
        "asset_place",
        "Put a catalog model (id from asset_find) into the 3D scene as a labelled object; downloads it on first use. "
        "fit is the longest side of the model in scene units (default 1). Returns the credit line to mention.",
        {"type": "object", "properties": {
            "id": {"type": "string"}, "pos": {**_VEC3, "description": "[x,y,z], default origin"},
            "fit": {"type": "number", "description": "longest side in scene units, default 1"},
            "label": {"type": "string"}}, "required": ["id"]},
        session.place, long=True, scheduling="WHEN_IDLE"))
    registry.register(Tool(
        "asset_credits", "List author and licence of every catalog model placed in this session.",
        {"type": "object", "properties": {}}, session.credits_tool))
    return session
