# backend/app/files/card.py
"""Build the `file_card` view data and the `file_ready` payload from stored file metadata."""

from typing import Any

from app.entities.shapes import shape_of_file
from app.files import store

SUMMARY_CHARS = 400
EXCERPT_CHARS = 6000
CARD_ROWS = 50


def summary_of(meta: dict[str, Any], text: str) -> str:
    if meta["kind"] in ("audio", "video", "binary") or meta.get("note"):
        return str(meta.get("note") or text.split("\n")[0])[:SUMMARY_CHARS]
    if meta["outline"]:
        return "; ".join(meta["outline"][:12])[:SUMMARY_CHARS]
    return " ".join(text.split())[:SUMMARY_CHARS]


def ready_payload(meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": meta["id"],
        "kind": meta["kind"],
        "name": meta["name"],
        "size": meta["bytes"],
        "url": store.download_url(meta["id"]),
        "meta": meta["meta"],
    }


def entity_args(meta: dict[str, Any]) -> dict[str, Any]:
    """add_entity arguments of a stored file (shared by file_to_scene, upload auto-placement and deck_place)."""
    pages = meta["meta"].get("pages")
    return {
        "ref_type": "file",
        "ref_id": meta["id"],
        "shape": shape_of_file(meta["kind"]),
        "title": meta["name"],
        "subtitle": f"{meta['kind']}" + (f", {pages} pages" if pages else ""),
    }


def card_data(meta: dict[str, Any], text: str) -> dict[str, Any]:
    tables = [{"name": t["name"], "columns": t["columns"], "rows": t["rows"][:CARD_ROWS]} for t in meta["tables"][:6]]
    data: dict[str, Any] = {
        "id": meta["id"],
        "name": meta["name"],
        "kind": meta["kind"],
        "size": meta["bytes"],
        "title": meta["title"],
        "summary": summary_of(meta, text),
        "meta": meta["meta"],
        "outline": meta["outline"][:40],
        "text_excerpt": text[:EXCERPT_CHARS],
        "truncated": meta["truncated"] or len(text) > EXCERPT_CHARS,
        "download_url": store.download_url(meta["id"]),
    }
    if tables:
        data["tables"] = tables
    if meta.get("note"):
        data["note"] = meta["note"]
    return data
