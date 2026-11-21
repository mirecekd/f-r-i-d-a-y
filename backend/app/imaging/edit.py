# backend/app/imaging/edit.py
"""edit_images: send stored photos to a Gemini image model and store the result as a new derived upload."""

import asyncio
import io
from typing import Any

from PIL import Image

from app import deck
from app.imaging.gemini_image import ImagingError, generate_image
from app.imaging.prompts import OPERATIONS, build_prompt
from app.tools_friday.ctx import Ctx
from app.vision import store
from app.vision.images import EXT_BY_MIME, MAX_BYTES, ImageRejected, inspect_image
from app.vision.upload import ready_payload

MAX_INPUTS = 6
MAX_INSTRUCTION = 2000


def _original(meta: dict[str, Any]) -> tuple[bytes, str]:
    return (store.uploads_dir() / f"{meta['id']}.{meta['ext']}").read_bytes(), meta["mime"]


def load_inputs(metas: list[dict[str, Any]], full_res: bool) -> list[tuple[bytes, str]]:
    """Bytes and mime per image: the 1600 px analysis copy unless `full_res`."""
    return [_original(m) if full_res else (store.analysis_jpeg(m["id"]), "image/jpeg") for m in metas]


def clean_image(data: bytes, mime: str) -> tuple[bytes, str]:
    """Re-encode without metadata (no EXIF, no text chunks); PNG stays PNG, anything else becomes JPEG."""
    with Image.open(io.BytesIO(data)) as im:
        im.load()
        out = io.BytesIO()
        if mime == "image/png":
            im.convert("RGBA" if "A" in im.mode else "RGB").save(out, "PNG")
            return out.getvalue(), "image/png"
        im.convert("RGB").save(out, "JPEG", quality=92)
        return out.getvalue(), "image/jpeg"


def save_derived(data: bytes, mime: str, name: str, provenance: dict[str, Any]) -> dict[str, Any]:
    """Store `data` as a normal upload (new uuid) and record where it came from."""
    if len(data) > MAX_BYTES:
        raise ImagingError(f"the result is larger than {MAX_BYTES // (1024 * 1024)} MB and was not stored")
    clean, clean_mime = clean_image(data, mime)
    try:
        meta = store.save(clean, f"{name}.{EXT_BY_MIME[clean_mime]}", inspect_image(clean, clean_mime))
    except ImageRejected as e:
        raise ImagingError(f"the result cannot be stored: {e}") from e
    meta["derived"] = provenance
    store.write_meta(meta)
    deck.register("image", meta["id"], meta["name"], str(provenance.get("instruction") or "")[:300], size=meta.get("bytes", 0),
                  thumb_url=store.url_of(meta), source="derived",
                  parent_ids=[deck.item_id("image", str(p)) for p in provenance.get("derived_from", [])],
                  meta={"derived": provenance, "w": meta.get("w"), "h": meta.get("h")}, created_at=meta.get("created"))
    return meta


def check_request(image_ids: Any, instruction: Any, operation: str) -> tuple[list[dict[str, Any]], str]:
    """The resolved source metadata and the trimmed instruction; ImagingError for anything the user must fix."""
    text = str(instruction or "").strip()
    if not text:
        raise ImagingError("instruction is empty: say what to do with the image(s)")
    if len(text) > MAX_INSTRUCTION:
        raise ImagingError(f"instruction is longer than {MAX_INSTRUCTION} characters")
    if operation not in OPERATIONS:
        raise ImagingError(f"unknown operation {operation!r}; use one of {', '.join(OPERATIONS)}")
    if not isinstance(image_ids, list) or not image_ids:
        raise ImagingError("image_ids must be a non-empty list (see list_images)")
    if len(image_ids) > MAX_INPUTS:
        raise ImagingError(f"at most {MAX_INPUTS} images per edit")
    metas = []
    for ref in image_ids:
        meta = store.resolve(ref)
        if meta is None:
            raise ImagingError(f"unknown image id {str(ref)[:40]!r}; call list_images")
        metas.append(meta)
    if operation == "merge_people" and len(metas) < 2:
        raise ImagingError("merge_people needs at least two images")
    return metas, text


async def edit_images(
    ctx: Ctx, image_ids: Any, instruction: Any, operation: str = "custom", model: str | None = None, full_res: bool = False
) -> dict[str, Any]:
    """Create a NEW image from the given ones; originals are untouched. Errors come back as {error}."""
    try:
        metas, text = check_request(image_ids, instruction, operation)
        inputs = await asyncio.to_thread(load_inputs, metas, full_res)
        used, data, mime = await generate_image(inputs, build_prompt(operation, text, len(inputs)), model)
        provenance = {"derived_from": [m["id"] for m in metas], "instruction": text, "operation": operation, "model": used}
        meta = await asyncio.to_thread(save_derived, data, mime, f"edited-{operation}", provenance)
    except ImagingError as e:
        return {"error": str(e)}
    except OSError as e:
        return {"error": f"image files could not be read or written: {type(e).__name__}"}
    await ctx.emit({"t": "image_ready", **ready_payload(meta), "derived": provenance})
    return {"ok": True, "image_id": meta["id"], "url": store.url_of(meta), "model": used, "bytes": meta["bytes"],
            "derived_from": provenance["derived_from"], "note": "AI-generated result; the originals are kept"}
