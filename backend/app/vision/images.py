# backend/app/vision/images.py
"""Validate an uploaded image by magic bytes and a real decode; extract EXIF; build the analysis copy."""

import io
import warnings
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageOps

from app.vision.exif import parse_exif

MAX_BYTES = 12 * 1024 * 1024
MAX_PIXELS = 40_000_000
ANALYSIS_SIDE = 1600
Image.MAX_IMAGE_PIXELS = MAX_PIXELS  # Pillow raises DecompressionBombError at twice this

EXT_BY_MIME = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}
MIME_BY_EXT = {ext: mime for mime, ext in EXT_BY_MIME.items()}
MIME_ALIASES = {"image/jpg": "image/jpeg", "image/pjpeg": "image/jpeg", "image/x-png": "image/png"}


class ImageRejected(ValueError):
    """The upload is not an acceptable image; the message is safe to show to the user."""


@dataclass
class Inspected:
    mime: str
    w: int
    h: int
    exif: dict[str, Any]
    analysis_jpeg: bytes


def sniff_mime(raw: bytes) -> str | None:
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    return None


def _flatten_to_rgb(im: Image.Image) -> Image.Image:
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        rgba = im.convert("RGBA")
        base = Image.new("RGB", rgba.size, "white")
        base.paste(rgba, mask=rgba.getchannel("A"))
        return base
    return im.convert("RGB")


def inspect_image(raw: bytes, declared_mime: str) -> Inspected:
    if not raw:
        raise ImageRejected("empty file")
    if len(raw) > MAX_BYTES:
        raise ImageRejected(f"image is larger than {MAX_BYTES // (1024 * 1024)} MB")
    sniffed = sniff_mime(raw)
    if sniffed is None:
        raise ImageRejected("content is not a jpeg, png, webp or gif image")
    declared = MIME_ALIASES.get(declared_mime.lower().strip(), declared_mime.lower().strip())
    if declared not in EXT_BY_MIME:
        raise ImageRejected(f"mime type {declared_mime[:40]!r} is not allowed (jpeg, png, webp, gif)")
    if declared != sniffed:
        raise ImageRejected("declared mime type does not match the file content")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            im = Image.open(io.BytesIO(raw))
            im.load()
    except Exception as e:  # Pillow raises many types on corrupt or bomb images
        raise ImageRejected(f"image cannot be decoded ({type(e).__name__})") from e
    exif = parse_exif(im)
    upright = ImageOps.exif_transpose(im)
    rgb = _flatten_to_rgb(upright)
    rgb.thumbnail((ANALYSIS_SIDE, ANALYSIS_SIDE), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    rgb.save(out, "JPEG", quality=85)
    return Inspected(sniffed, upright.width, upright.height, exif, out.getvalue())
