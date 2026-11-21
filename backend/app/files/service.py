# backend/app/files/service.py
"""Per-connection file state: WebSocket file_upload, file_ready, file_card views, voice hint to Live."""

import asyncio
import base64
import binascii
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.files import store
from app.files.card import card_data, ready_payload
from app.files.common import MAX_BYTES, ExtractError
from app.files.extract import extract
from app.files.kinds import detect
from app.tools_friday.ctx import Ctx
from app.views import ViewError, view_msg
from app.vision.images import ImageRejected
from app.vision.service import VisionService

log = logging.getLogger("friday.files")
MAX_B64_CHARS = (MAX_BYTES + 2) // 3 * 4 + 4
VoiceHint = Callable[[str], Awaitable[None]]


async def ingest(raw: bytes, name: object) -> dict[str, Any]:
    """Extract (off the event loop) and store one non-image file; raises ExtractError."""

    def work() -> dict[str, Any]:
        return store.save(raw, name, extract(raw, str(name or "")))

    return await asyncio.to_thread(work)


def attach_hint(meta: dict[str, Any]) -> str:
    pages = meta["meta"].get("pages")
    size = f", {pages} pages" if pages else ""
    return f"User attached {meta['name']} ({meta['kind']}{size}); use read_file to read it (file_id {meta['id']})"


class FileService:
    """Routes uploads: images to the vision service, everything else to the extractors."""

    def __init__(self, ctx: Ctx, vision: VisionService):
        self.ctx = ctx
        self.vision = vision

    async def on_upload(self, msg: dict[str, Any], voice_hint: VoiceHint | None = None) -> None:
        """Handle `{t:'file_upload'|'image_upload', id?, name, mime, data_b64, analyze?}`.

        `voice_hint` is given while a Live session is active; it tells the model about the file without a reply."""
        if msg.get("t") == "image_upload":
            return await self.vision.on_upload(msg)  # the old message keeps the old image-only path
        client_id = msg.get("id")
        extra = {"id": client_id} if client_id else {}
        data_b64 = msg.get("data_b64")
        if not isinstance(data_b64, str) or len(data_b64) > MAX_B64_CHARS:
            return await self.ctx.emit({"t": "error", "message": f"file_upload: file is missing or larger than "
                                        f"{MAX_BYTES // (1024 * 1024)} MB", **extra})
        try:
            raw = base64.b64decode(data_b64, validate=True)
        except (binascii.Error, ValueError):
            return await self.ctx.emit({"t": "error", "message": "file_upload: data_b64 is not valid base64", **extra})
        if detect(raw, str(msg.get("name") or ""))[0] == "image":
            return await self.vision.on_upload(msg)
        try:
            meta = await ingest(raw, msg.get("name"))
        except (ExtractError, ImageRejected) as e:
            return await self.ctx.emit({"t": "error", "message": f"file_upload: {e}", **extra})
        await self.ctx.emit({"t": "file_ready", **ready_payload(meta), **({"client_id": client_id} if client_id else {})})
        await self.show_card(meta)
        if voice_hint:
            await voice_hint(attach_hint(meta))

    async def show_card(self, meta: dict[str, Any]) -> dict[str, Any]:
        """Emit the file_card view for a stored file; returns {ok, view_id} or {error}."""
        try:
            text = await asyncio.to_thread(store.text_of, meta["id"])
            msg = view_msg("file_card", card_data(meta, text), meta["name"], f"file-{meta['id'][:8]}")
        except (ViewError, OSError) as e:
            log.warning("file_card rejected: %s", e)
            return {"error": f"cannot show the file tile: {e}"[:200]}
        await self.ctx.emit(msg)
        return {"ok": True, "view_id": msg["id"]}


