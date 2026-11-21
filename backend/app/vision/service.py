# backend/app/vision/service.py
"""Per-connection vision state: WebSocket image_upload, background analysis, image_card views."""

import asyncio
import base64
import binascii
import logging
from collections.abc import Callable
from typing import Any

from app.agent.llm import LlmError
from app.scene_schema import SceneError
from app.tools_friday.ctx import Ctx
from app.views import ViewError, view_msg
from app.vision import store
from app.vision.analyze import analyze_picture
from app.vision.images import MAX_BYTES, ImageRejected
from app.vision.parse import AnalysisParseError
from app.vision.upload import ingest, ready_payload

log = logging.getLogger("friday.vision")
MAX_B64_CHARS = (MAX_BYTES + 2) // 3 * 4 + 4
LONG_SIDE = 3.0  # scene units of the longer image edge when scale is 1


def card_data(meta: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    """image_card view data: the documented fields plus the optional scene/location/rooms extras."""
    keys = ("kind", "summary", "people_count", "objects", "text_found", "notes")
    extras = ("scene", "location_hint", "rooms", "dimensions_hint", "confidence")
    return {
        "url": store.url_of(meta),
        **{k: analysis[k] for k in keys},
        "exif": meta["exif"],
        **{k: analysis[k] for k in extras if analysis.get(k) not in (None, [])},
    }


class VisionService:
    """Owns the uploads of one browser connection; `model_for` returns the pinned agent model."""

    def __init__(self, ctx: Ctx, model_for: Callable[[], str]):
        self.ctx = ctx
        self.model_for = model_for
        self._jobs: dict[str, asyncio.Task] = {}
        self._background: set[asyncio.Task] = set()

    async def analyze(self, meta: dict[str, Any], force: bool = False) -> dict[str, Any]:
        """The analysis of one stored image (cached in its metadata); emits the image_card view when computed."""
        if meta.get("analysis") and not force:
            return meta["analysis"]
        job = self._jobs.get(meta["id"])
        if job is None:
            job = self._jobs[meta["id"]] = asyncio.create_task(self._run(meta))
            job.add_done_callback(lambda _t, i=meta["id"]: self._jobs.pop(i, None))
        return await asyncio.shield(job)

    async def _run(self, meta: dict[str, Any]) -> dict[str, Any]:
        jpeg = await asyncio.to_thread(store.analysis_jpeg, meta["id"])
        model, analysis = await analyze_picture(jpeg, meta["exif"], self.model_for())
        meta["analysis"] = {**analysis, "model": model}
        await asyncio.to_thread(store.write_meta, meta)
        try:
            msg = view_msg("image_card", card_data(meta, analysis), meta["name"], f"image-{meta['id'][:8]}")
        except ViewError as e:
            log.warning("image_card rejected: %s", e)
        else:
            await self.ctx.emit(msg)
        return meta["analysis"]

    async def on_upload(self, msg: dict[str, Any]) -> None:
        """Handle `{t:'image_upload', id?, name, mime, data_b64, analyze?}`: store, announce, analyze in background."""
        client_id = msg.get("id")
        data_b64 = msg.get("data_b64")
        try:
            if not isinstance(data_b64, str) or len(data_b64) > MAX_B64_CHARS:
                raise ImageRejected(f"image is missing or larger than {MAX_BYTES // (1024 * 1024)} MB")
            try:
                raw = base64.b64decode(data_b64, validate=True)
            except (binascii.Error, ValueError) as e:
                raise ImageRejected("data_b64 is not valid base64") from e
            meta = await ingest(raw, msg.get("name"), str(msg.get("mime", "")))
        except ImageRejected as e:
            await self.ctx.emit({"t": "error", "message": f"image_upload: {e}", **({"id": client_id} if client_id else {})})
            return
        await self.ctx.emit({"t": "image_ready", **ready_payload(meta), **({"client_id": client_id} if client_id else {})})
        if msg.get("analyze") is not False:
            task = asyncio.create_task(self._analyze_in_background(meta))
            self._background.add(task)
            task.add_done_callback(self._background.discard)

    async def _analyze_in_background(self, meta: dict[str, Any]) -> None:
        try:
            analysis = await self.analyze(meta)
        except (LlmError, AnalysisParseError, OSError) as e:
            log.warning("image analysis failed: %s", type(e).__name__)
            await self.ctx.emit({"t": "error", "message": f"image analysis failed: {type(e).__name__}: {e}"[:300]})
        else:
            await self.ctx.emit({"t": "notice", "text": f"Image analysed: {analysis['summary'][:120]}"})

    async def show_in_scene(self, image_id: Any, pos: Any = None, scale: Any = None) -> dict[str, Any]:
        """Add the stored image to the scene as an `image` object sized by its aspect ratio and emit the scene op."""
        meta = store.resolve(image_id)
        if meta is None:
            return {"error": "unknown image_id; call list_images"}
        aspect = meta["w"] / meta["h"]
        w, h = (LONG_SIDE, LONG_SIDE / aspect) if aspect >= 1 else (LONG_SIDE * aspect, LONG_SIDE)
        obj: dict[str, Any] = {
            "id": f"img-{meta['id'][:8]}", "kind": "image", "url": store.url_of(meta),
            "w": round(w, 3), "h": round(h, 3), "label": meta["name"],
            "pos": pos or [0, h / 2 + 0.1, 0],
        }
        if scale is not None:
            obj["scale"] = scale
        ops = [{"op": "add", "obj": obj}]
        try:
            self.ctx.scene.apply(ops)
        except SceneError as e:
            return {"error": str(e)}
        await self.ctx.emit({"t": "scene", "ops": ops})
        return {"ok": True, "object_id": obj["id"], "w": obj["w"], "h": obj["h"]}

    async def on_image_to_scene(self, msg: dict[str, Any]) -> None:
        """Handle `{t:'image_to_scene', id}` (the image_card button): same as the show_in_scene tool; errors go to the chat."""
        result = await self.show_in_scene(msg.get("id"))
        if "error" in result:
            await self.ctx.emit({"t": "error", "message": f"image_to_scene: {result['error']}"})

    async def close(self) -> None:
        tasks = [*self._background, *self._jobs.values()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
