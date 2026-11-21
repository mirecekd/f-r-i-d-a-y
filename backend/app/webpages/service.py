# backend/app/webpages/service.py
"""Per-connection web page service: fetch, extract, store, register and place a page; PDFs and images go to their pipelines."""

import asyncio
import base64
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.deck.items import item_id
from app.deck.session import DeckSession
from app.tools_friday.ctx import Ctx
from app.webpages import fetch as web_fetch
from app.webpages import store
from app.webpages.extract import extract_html, extract_plain
from app.webpages.urlguard import UrlRefused

log = logging.getLogger("friday.web")
Fetcher = Callable[[str], Awaitable[web_fetch.Fetched]]


class WebService:
    def __init__(self, ctx: Ctx, deck: DeckSession, files: Any, vision: Any, fetcher: Fetcher = web_fetch.fetch) -> None:
        self.ctx, self.deck, self.files, self.vision, self.fetcher = ctx, deck, files, vision, fetcher

    async def add(self, url: object, place: bool = True) -> dict[str, Any]:
        """Fetch and keep one page; returns {ok, id, title, ...} or {error}. Never raises."""
        try:
            got = await self.fetcher(str(url or ""))
            if got.content_type == web_fetch.PDF_TYPE or got.content_type in web_fetch.IMAGE_TYPES:
                return await self._hand_over(got)
            extracted = await asyncio.to_thread(self._extract, got)
            meta = await asyncio.to_thread(store.save, got.url, len(got.body), got.content_type, extracted)
        except UrlRefused as e:
            return {"error": f"cannot add the page: {e}"[:300]}
        except OSError as e:
            return {"error": f"cannot store the page: {e}"[:300]}
        out: dict[str, Any] = {
            "ok": True, "id": item_id("web", meta["id"]), "web_id": meta["id"], "title": meta["title"],
            "url": meta["url"], "chars": meta["chars"], "fetch_count": meta["fetch_count"],
        }
        if place:
            placed = await self.deck.place(out["id"])
            out["placed"] = "error" not in placed
            if "error" in placed:
                out["place_error"] = placed["error"]
        return out

    @staticmethod
    def _extract(got: web_fetch.Fetched) -> dict[str, Any]:
        if got.content_type == "text/plain":
            return extract_plain(got.body, got.charset)
        return extract_html(got.body, got.url, got.charset)

    async def _hand_over(self, got: web_fetch.Fetched) -> dict[str, Any]:
        """A PDF becomes a normal file, an image a normal uploaded image: the existing pipelines place and read them."""
        name = got.url.rstrip("/").rsplit("/", 1)[-1].split("?")[0] or "download"
        msg = {"name": name, "mime": got.content_type, "data_b64": base64.b64encode(got.body).decode("ascii")}
        if got.content_type == web_fetch.PDF_TYPE:
            await self.files.on_upload({"t": "file_upload", **msg})
            return {"ok": True, "handed_to": "files", "name": name, "note": "the PDF is on the desk like a dropped file; use read_file"}
        await self.vision.on_upload({"t": "image_upload", **msg})
        return {"ok": True, "handed_to": "vision", "name": name, "note": "the image is on the desk like a dropped image"}

    async def refresh(self, ref: object) -> dict[str, Any]:
        page = self.find(ref)
        if page is None:
            return {"error": "unknown web page; call deck_list with type web"}
        return await self.add(page["url"], place=False)

    @staticmethod
    def find(ref: object) -> dict[str, Any] | None:
        """A stored page by deck id (d...), web id or prefix of either."""
        from app.deck import query

        text = str(ref or "").strip()
        item = query.resolve(text) if text else None
        if item is not None and item["type"] == "web":
            return store.resolve(item["ref_id"])
        return store.resolve(text)

    async def on_message(self, msg: dict[str, Any]) -> None:
        """Browser `{t:'web_add', url}`; a failure becomes an `error` message."""
        result = await self.add(msg.get("url"))
        if "error" in result:
            await self.ctx.emit({"t": "error", "message": result["error"]})
