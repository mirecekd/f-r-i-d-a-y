# backend/app/files/upload.py
"""HTTP side of non-image files: POST /api/upload/file and GET /api/files/<id> (download only)."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from app.deck import desk
from app.files import store
from app.files.card import entity_args, ready_payload
from app.files.common import MAX_BYTES, ExtractError
from app.files.service import ingest

router = APIRouter()


async def ingest_http(raw: bytes, name: object) -> JSONResponse:
    if len(raw) > MAX_BYTES:
        return JSONResponse({"error": f"file is larger than {MAX_BYTES // (1024 * 1024)} MB"}, status_code=413)
    try:
        meta = await ingest(raw, name)
    except ExtractError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    await desk.announce_and_place({"t": "file_ready", **ready_payload(meta)}, entity_args(meta))
    return JSONResponse(ready_payload(meta))


@router.get("/api/files/{file_id}")
async def download(file_id: str):
    meta = store.load(file_id)
    path = store.original_path(file_id)
    if meta is None or path is None:
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type="application/octet-stream", filename=meta["name"], headers={
        "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'; sandbox",
        "Cache-Control": "private, max-age=31536000, immutable",
    }, content_disposition_type="attachment")


