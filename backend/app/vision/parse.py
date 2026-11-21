# backend/app/vision/parse.py
"""Turn the vision model's reply into a validated analysis dict (strict JSON schema, tolerant of fences)."""

import json
import re
from typing import Any

KINDS = ("photo", "floorplan", "screenshot", "drawing", "document", "other")
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class AnalysisParseError(ValueError):
    pass


def extract_json(text: str) -> dict[str, Any]:
    """The first JSON object in `text`, with markdown fences and surrounding prose removed."""
    cleaned = _FENCE.sub("", text.strip())
    start = cleaned.find("{")
    if start < 0:
        raise AnalysisParseError("no JSON object in the reply")
    try:
        obj, _ = json.JSONDecoder().raw_decode(cleaned[start:])
    except json.JSONDecodeError as e:
        raise AnalysisParseError(f"invalid JSON: {e.msg}") from e
    if not isinstance(obj, dict):
        raise AnalysisParseError("the JSON value is not an object")
    return obj


def _str(value: Any, limit: int) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _opt_str(value: Any, limit: int) -> str | None:
    return _str(value, limit) or None


def _count(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    return int(value)


def _objects(value: Any) -> list[dict[str, Any]]:
    out = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, dict) and _str(item.get("label"), 80):
            out.append({"label": _str(item["label"], 80), "count": _count(item.get("count")) or 1})
        elif isinstance(item, str) and item.strip():
            out.append({"label": item.strip()[:80], "count": 1})
    return out[:40]


def _rooms(value: Any) -> list[dict[str, Any]]:
    out = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, str) and item.strip():
            out.append({"name": item.strip()[:80], "dimensions": None})
        elif isinstance(item, dict) and _str(item.get("name"), 80):
            dims = item.get("dimensions") or item.get("size")
            out.append({"name": _str(item["name"], 80), "dimensions": _opt_str(dims, 80)})
    return out[:40]


def normalize(raw: dict[str, Any]) -> dict[str, Any]:
    """Coerce to the documented shape; a missing or empty `summary` is an error so the caller can retry."""
    summary = _str(raw.get("summary"), 1500)
    if not summary:
        raise AnalysisParseError("summary is missing")
    kind = _str(raw.get("kind"), 20).lower()
    conf = raw.get("confidence")
    texts = raw.get("text_found")
    return {
        "kind": kind if kind in KINDS else "other",
        "summary": summary,
        "people_count": _count(raw.get("people_count")),
        "objects": _objects(raw.get("objects")),
        "text_found": [_str(t, 200) for t in texts if _str(t, 200)][:30] if isinstance(texts, list) else [],
        "scene": _opt_str(raw.get("scene"), 200),
        "location_hint": _opt_str(raw.get("location_hint"), 200),
        "rooms": _rooms(raw.get("rooms")),
        "dimensions_hint": _opt_str(raw.get("dimensions_hint"), 300),
        "confidence": round(min(max(float(conf), 0.0), 1.0), 2)
        if isinstance(conf, (int, float)) and not isinstance(conf, bool)
        else None,
        "notes": _str(raw.get("notes"), 600),
    }


def parse_analysis(text: str) -> dict[str, Any]:
    return normalize(extract_json(text))
