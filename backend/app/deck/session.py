# backend/app/deck/session.py
"""Per-connection deck endpoint: browser messages deck_list / deck_open / deck_pin / deck_tag and `deck_changed` pushes."""

import asyncio
import logging
from typing import Any

from app.deck import desk, notify, query, registry
from app.deck.items import TYPES, DeckError
from app.deck.opener import Opener
from app.deck.place import place_item
from app.files.service import FileService
from app.model3d.session import ModelSession
from app.tools_friday.ctx import Ctx
from app.vision.service import VisionService

log = logging.getLogger("friday.deck")
PAGE = 60


class DeckSession:
    def __init__(self, ctx: Ctx, models: ModelSession, files: FileService, vision: VisionService) -> None:
        self.ctx, self.emit = ctx, ctx.emit
        self.opener = Opener(ctx, models, files, vision)
        desk.attach(ctx)
        self._loop: asyncio.AbstractEventLoop | None = None  # bound by the first message (tests build sessions without a loop)
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
        self._tasks: set[asyncio.Task] = set()
        notify.subscribe(self._changed)

    def _changed(self, deck_id: str) -> None:
        """Called from any thread when an item changed: push {t:'deck_changed'} on the connection's loop."""
        def push() -> None:
            async def send() -> None:
                await self.emit({"t": "deck_changed", "id": deck_id})

            task = asyncio.get_running_loop().create_task(send())
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

        loop = self._loop
        if loop is None:
            return
        if loop.is_closed():
            raise RuntimeError("connection closed")
        loop.call_soon_threadsafe(push)

    def close(self) -> None:
        notify.unsubscribe(self._changed)
        desk.detach(self.ctx)
        for task in list(self._tasks):
            task.cancel()

    async def handle(self, msg: dict[str, Any]) -> None:
        """Dispatch one `deck_*` browser message; failures become an `error` message."""
        self._loop = asyncio.get_running_loop()
        try:
            await self._dispatch(str(msg.get("t")), msg)
        except DeckError as e:
            await self.emit({"t": "error", "message": f"deck: {e}"})

    async def _dispatch(self, kind: str, msg: dict[str, Any]) -> None:
        if kind == "deck_list":
            await self.emit(await asyncio.to_thread(self.listing, msg))
        elif kind == "deck_open":
            result = await self.opener.open(msg.get("id"))
            if "error" in result:
                await self.emit({"t": "error", "message": result["error"]})
        elif kind == "deck_place":
            result = await self.place(msg.get("id"), msg.get("pos"))
            if "error" in result:
                await self.emit({"t": "error", "message": f"deck_place: {result['error']}"})
        elif kind == "deck_pin":
            await asyncio.to_thread(registry.update, self._id(msg), pinned=bool(msg.get("pinned")))
        elif kind == "deck_tag":
            await asyncio.to_thread(registry.update, self._id(msg), tags=msg.get("tags") or [])
        elif kind == "deck_forget":
            # The browser button already asks twice; this removes the registry row only, never the stored file or model.
            deck_id = self._id(msg)
            await asyncio.to_thread(registry.delete, deck_id, False)
            await self.emit({"t": "deck_changed", "id": deck_id})

    async def place(self, ref: object, pos: Any = None) -> dict[str, Any]:
        """Put the item on the desk as an entity (or frame it when it is already there); returns {ok, ...} or {error}."""
        item = await asyncio.to_thread(query.resolve, ref)
        if item is None:
            return {"error": "unknown deck item; call deck_list or deck_find"}
        return await place_item(self.ctx, item, pos)

    @staticmethod
    def _id(msg: dict[str, Any]) -> str:
        item = query.resolve(msg.get("id"))
        if item is None:
            raise DeckError("unknown item")
        return item["id"]

    @staticmethod
    def listing(msg: dict[str, Any]) -> dict[str, Any]:
        """The `deck` answer: one page of items, the total of the filter and the registry stats."""
        type_ = msg.get("type") if msg.get("type") in TYPES else None
        q = msg.get("q") if isinstance(msg.get("q"), str) else None
        raw_offset = msg.get("offset")
        offset = max(0, raw_offset) if isinstance(raw_offset, int) else 0
        items = query.list_items(type_, q, None, None, PAGE, offset)
        return {"t": "deck", "items": items, "total": query.count_items(type_, q), "offset": offset,
                "q": q or "", "type": type_, "stats": query.stats()}
