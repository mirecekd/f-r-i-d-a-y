# backend/app/views.py
"""Builders for rich view panels (`view` / `view_close` WebSocket messages)."""

import json
import uuid

VIEW_KINDS = frozenset(
    {"image", "chart", "table", "markdown", "code", "diagram", "map", "json", "memory_graph", "image_card", "file_card"}
)
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024


class ViewError(ValueError):
    """Raised when a view request is malformed or too large."""


def view_msg(kind: str, data: object, title: str | None = None, id: str | None = None) -> dict:
    """Validate kind and payload size, return the `view` message dict."""
    if kind not in VIEW_KINDS:
        raise ViewError(f"unknown view kind: {kind!r} (expected one of {sorted(VIEW_KINDS)})")
    try:
        size = len(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError) as e:
        raise ViewError(f"view data is not JSON serializable: {e}") from e
    if size > MAX_PAYLOAD_BYTES:
        raise ViewError(f"view data too large: {size} bytes (max {MAX_PAYLOAD_BYTES})")
    msg: dict = {"t": "view", "id": id or uuid.uuid4().hex[:8], "kind": kind, "data": data}
    if title:
        msg["title"] = title
    return msg


def view_close_msg(id: str) -> dict:
    return {"t": "view_close", "id": id}
