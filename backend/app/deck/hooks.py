# backend/app/deck/hooks.py
"""One-call hooks the stores use to register what they save. They never raise: the deck must not break a save."""

import hashlib
import logging
from typing import Any

from app.deck import registry

log = logging.getLogger("friday.deck")
MAX_MEMORY_SEARCHES = 50


def _safe(label: str, fn: Any, *args: Any, **kw: Any) -> None:
    try:
        fn(*args, **kw)
    except Exception as e:
        log.warning("deck hook %s failed: %s: %s", label, type(e).__name__, e)


def image_saved(meta: dict[str, Any]) -> None:
    """Called from vision `write_meta` (upload and again once the analysis is stored)."""
    _safe("image", _image, meta)


def _image(meta: dict[str, Any]) -> None:
    a = meta.get("analysis") or {}
    objects = " ".join(str(o.get("label", "")) for o in a.get("objects") or [] if isinstance(o, dict))
    text = " ".join([str(a.get("summary") or ""), objects, " ".join(map(str, a.get("text_found") or []))]).strip()
    subtitle = str(a.get("summary") or f"{meta.get('w')} x {meta.get('h')} px")
    registry.register("image", meta["id"], meta.get("name") or "image", subtitle, size=meta.get("bytes", 0),
                      thumb_url=f"/api/uploads/{meta['id']}.{meta['ext']}", source="upload", text=text,
                      created_at=meta.get("created"), meta={"w": meta.get("w"), "h": meta.get("h"), "mime": meta.get("mime")})


def file_saved(meta: dict[str, Any], text: str) -> None:
    """Called from files `save` with the extracted text."""
    _safe("file", lambda: registry.register(
        "file", meta["id"], meta.get("title") or meta["name"], f"{meta['name']} - {meta['kind']}", size=meta.get("bytes", 0),
        source="upload", text=text, created_at=meta.get("created"), meta={"name": meta["name"], "kind": meta["kind"]}))


def model_saved(model: Any) -> None:
    """Called from ModelStore `save` (create, every committed edit, undo)."""
    names = " ".join(p.name for p in model.parts.values() if p.name)
    _safe("model3d", lambda: registry.register(
        "model3d", model.id, model.id, f"{len(model.parts)} parts, {model.units}", size=len(model.parts),
        source="generated", text=names, meta={"units": model.units, "parts": len(model.parts)}))


def model_removed(model_id: str) -> None:
    """Called from ModelStore `delete`: the model is gone, so its registry row goes too."""
    from app.deck.items import item_id

    _safe("model3d-delete", lambda: registry.delete(item_id("model3d", model_id)))


def memory_search_done(query: str, project: str | None, data: dict[str, Any]) -> None:
    """Called after a query-focused memory graph was built; keeps the newest 50 searches."""
    def go() -> None:
        ref = hashlib.sha256(f"{query}|{project or ''}".encode()).hexdigest()[:24]
        nodes = len(data.get("nodes") or [])
        registry.register("memory_graph", ref, f"Memory: {query}"[:120], f"{nodes} nodes" + (f", {project}" if project else ""),
                          size=nodes, source="tool", text=str(data.get("summary") or "")[:1000],
                          meta={"query": query, "project": project})
        registry.prune("memory_graph", MAX_MEMORY_SEARCHES)

    _safe("memory_graph", go)
