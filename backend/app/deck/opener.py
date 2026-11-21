# backend/app/deck/opener.py
"""Open a deck item: emit the existing view that belongs to its type."""

import asyncio
from typing import Any

from app.deck import query
from app.deck.items import DeckError
from app.entities.open import open_ref
from app.files.service import FileService
from app.memory.handlers import memory_search
from app.model3d.model import ModelError
from app.model3d.session import ModelSession
from app.tools_friday.ctx import Ctx
from app.views import ViewError, view_msg
from app.vision.service import VisionService


class Opener:
    """Per-connection: needs the connection's context, model session and the file and vision services."""

    def __init__(self, ctx: Ctx, models: ModelSession, files: FileService, vision: VisionService) -> None:
        self.ctx, self.emit, self.models, self.files, self.vision = ctx, ctx.emit, models, files, vision

    async def open(self, ref: object) -> dict[str, Any]:
        """Show the item; returns {ok, id, type, view?} or {error}. Never raises."""
        item = query.resolve(ref)
        if item is None:
            return {"error": f"unknown deck item {str(ref)[:40]!r}; call deck_list to see the ids"}
        try:
            shown = await self._by_type(item)
        except (DeckError, ModelError, ViewError, OSError, KeyError) as e:
            return {"error": f"cannot open '{item['title']}': {e}"[:300]}
        return {"ok": True, "id": item["id"], "type": item["type"], **shown}

    async def open_by_args(self, args: dict[str, Any]) -> dict[str, Any]:
        """Tool handler form of `open`."""
        return await self.open(args.get("id"))

    async def _by_type(self, item: dict[str, Any]) -> dict[str, Any]:
        kind, ref = item["type"], item["ref_id"]
        if kind in ("image", "file", "web"):
            shown = await open_ref(self.ctx, self.vision, self.files, {"type": kind, "id": ref})  # same builders as entity_open
            if "error" in shown:
                raise DeckError(shown["error"])
            return {"view": "image_card" if kind == "image" else "file_card", **{k: v for k, v in shown.items() if k != "ok"}}
        if kind == "workshop":
            from app.workshop.deck_hooks import enter_for

            shown = await enter_for(self.ctx, ref)
            if "error" in shown:
                raise DeckError(shown["error"])
            return {"view": "workshop", "workshop": ref}
        if kind == "model3d":
            model = await asyncio.to_thread(self.models.store.load, ref)
            await self.models.redraw(model, {})
            return {"view": "scene", "model": model.id}
        if kind == "memory_graph":
            await memory_search(self.emit, {"query": item["meta"].get("query"), "project": item["meta"].get("project")})
            return {"view": "memory_graph"}
        if kind == "note":
            return await self._show("markdown", {"text": item["meta"].get("text") or item["subtitle"] or item["title"]}, item)
        if kind == "view":
            shown = item["meta"].get("view")
            if not isinstance(shown, dict) or "kind" not in shown:
                raise DeckError("this view was not stored with its content")
            return await self._show(shown["kind"], shown.get("data"), item)
        raise DeckError(f"items of type '{kind}' cannot be opened yet")

    async def _show(self, kind: str, data: Any, item: dict[str, Any]) -> dict[str, Any]:
        msg = view_msg(kind, data, item["title"], f"deck-{item['id']}")
        await self.emit(msg)
        return {"view": kind, "view_id": msg["id"]}
