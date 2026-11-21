# backend/app/vision/exif.py
"""Parsed EXIF fields only: raw EXIF blobs are never stored in metadata nor shown to a model."""

import math
import re
from typing import Any

from PIL import Image

EXIF_IFD, GPS_IFD = 0x8769, 0x8825
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_STAMP = re.compile(r"^(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2}):(\d{2})")


def _text(value: Any) -> str | None:
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    if not isinstance(value, str):
        return None
    cleaned = _CONTROL.sub("", value).strip()[:80]
    return cleaned or None


def _stamp(value: Any) -> str | None:
    m = _STAMP.match(value) if isinstance(value, str) else None
    return "{}-{}-{}T{}:{}:{}".format(*m.groups()) if m else None


def _degrees(dms: Any, ref: Any, limit: float) -> float | None:
    try:
        d, m, s = (float(x) for x in dms)
        sign = -1 if str(ref).upper() in ("S", "W", "B'S'", "B'W'") else 1
        deg = sign * (d + m / 60 + s / 3600)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return round(deg, 6) if math.isfinite(deg) and abs(deg) <= limit else None


def parse_exif(im: Image.Image) -> dict[str, Any]:
    """{camera_make?, camera_model?, taken_at?, orientation?, lat?, lon?}; empty when there is nothing usable."""
    try:
        exif = im.getexif()
        sub, gps = dict(exif.get_ifd(EXIF_IFD)), dict(exif.get_ifd(GPS_IFD))
    except Exception:
        return {}
    out: dict[str, Any] = {}
    for key, value in (("camera_make", _text(exif.get(271))), ("camera_model", _text(exif.get(272)))):
        if value:
            out[key] = value
    taken = _stamp(sub.get(36867)) or _stamp(sub.get(36868)) or _stamp(exif.get(306))
    if taken:
        out["taken_at"] = taken
    orientation = exif.get(274)
    if isinstance(orientation, int) and 1 <= orientation <= 8:
        out["orientation"] = orientation
    lat, lon = _degrees(gps.get(2), gps.get(1), 90), _degrees(gps.get(4), gps.get(3), 180)
    if lat is not None and lon is not None and (lat, lon) != (0.0, 0.0):
        out["lat"], out["lon"] = lat, lon
    return out
