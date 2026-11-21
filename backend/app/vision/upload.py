# backend/app/vision/upload.py
"""HTTP side of image upload: POST /api/upload (multipart) and GET /api/uploads/<uuid>.<ext>."""

import asyncio

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.vision import store
from app.vision.images import MAX_BYTES, MIME_BY_EXT, ImageRejected, inspect_image

router = APIRouter()
SERVE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; sandbox",
    "Cache-Control": "private, max-age=31536000, immutable",
}


def ready_payload(meta: dict) -> dict:
    return {"id": meta["id"], "url": store.url_of(meta), "w": meta["w"], "h": meta["h"], "exif": meta["exif"]}


async def ingest(raw: bytes, name: object, mime: str) -> dict:
    """Validate, store and describe one image; raises ImageRejected. Pillow work runs off the event loop."""

    def work() -> dict:
        return store.save(raw, name, inspect_image(raw, mime))

    return await asyncio.to_thread(work)


@router.post("/api/upload")
async def upload(file: UploadFile, request: Request):
    """Store an image; analysis is not started here (use the analyze_image tool or the WebSocket upload)."""
    if int(request.headers.get("content-length") or 0) > MAX_BYTES + 64 * 1024:
        return JSONResponse({"error": "image is larger than 12 MB"}, status_code=413)
    raw = await file.read(MAX_BYTES + 1)
    try:
        meta = await ingest(raw, file.filename, file.content_type or "")
    except ImageRejected as e:
        return JSONResponse({"error": str(e)}, status_code=413 if "larger" in str(e) else 400)
    return ready_payload(meta)


@router.get("/api/uploads/{filename}")
async def serve(filename: str):
    m = store.FILE_RE.fullmatch(filename)
    if not m:
        raise HTTPException(status_code=404)
    path = store.uploads_dir() / f"{m.group(1)}.{m.group(2)}"  # rebuilt from the validated groups only
    if not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(
        path, media_type=MIME_BY_EXT[m.group(2)], headers={**SERVE_HEADERS, "Content-Disposition": "inline"}
    )
