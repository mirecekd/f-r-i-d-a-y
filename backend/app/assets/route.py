# backend/app/assets/route.py
"""GET /assets/models/<id>.glb: serves a cached model. The id must match a strict regex AND be in the index; the file path is
built from the validated id only, never from the request path."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.assets import index

router = APIRouter()


@router.get("/asset-models/{name}")
async def asset_model(name: str) -> FileResponse:
    stem, dot, ext = name.rpartition(".")
    asset = index.get(stem) if dot and ext == "glb" else None
    if asset is None:
        raise HTTPException(404, "unknown model")
    path = index.file_of(asset.id)
    if not path.is_file():
        raise HTTPException(404, "model not downloaded yet")
    return FileResponse(path, media_type="model/gltf-binary", headers={"Cache-Control": "public, max-age=86400"})
