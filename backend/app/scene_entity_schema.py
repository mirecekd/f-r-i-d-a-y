# backend/app/scene_entity_schema.py
"""Validation of the entity-related scene props: `ref`, entity `shape`, `style` and link endpoints."""

import re

from app.scene_errors import SceneError

REF_TYPES = ("image", "file", "model", "memory", "tool", "workshop", "web")
SHAPES = ("image", "doc", "book", "table", "code", "audio", "archive", "tool", "model", "note", "workshop")
LINK_STYLES = ("solid", "dashed")
MAX_REF_ID = 80
_REF_ID = re.compile(r"[A-Za-z0-9_.:-]+")


def check_ref(v: object) -> None:
    """`ref` names a stored item: {type, id}; the id may not contain path characters."""
    if not isinstance(v, dict) or set(v) != {"type", "id"}:
        raise SceneError("ref must be {type, id}")
    if v["type"] not in REF_TYPES:
        raise SceneError(f"ref.type must be one of {list(REF_TYPES)}")
    rid = v["id"]
    if not isinstance(rid, str) or not rid or len(rid) > MAX_REF_ID:
        raise SceneError(f"ref.id must be a string of 1..{MAX_REF_ID} characters")
    if not _REF_ID.fullmatch(rid) or ".." in rid:
        raise SceneError("ref.id may only contain letters, digits and _ . : -")


def check_entity_value(kind: str | None, name: str, v: object) -> bool:
    """Validate the props this module owns; returns True when `name` was handled here."""
    if name == "ref":
        check_ref(v)
    elif name == "shape":
        if v not in SHAPES:
            raise SceneError(f"shape must be one of {list(SHAPES)}")
    elif name == "style":
        if v not in LINK_STYLES:
            raise SceneError(f"style must be one of {list(LINK_STYLES)}")
    elif name in ("from", "to") and (kind == "link" or (kind is None and isinstance(v, str))):
        if not isinstance(v, str) or not 0 < len(v) <= 200:
            raise SceneError(f"{name} must be an object id")
    else:
        return False
    return True
