# backend/app/webpages/card.py
"""The card (`file_card` view data) and the desk entity arguments of a stored web page."""

import time
from typing import Any

SUMMARY_CHARS = 400
EXCERPT_CHARS = 6000
CARD_OUTLINE = 40


def entity_args(meta: dict[str, Any]) -> dict[str, Any]:
    """add_entity arguments of a stored page (used by deck_place and web_add)."""
    return {"ref_type": "web", "ref_id": meta["id"], "shape": "doc", "title": meta["title"], "subtitle": meta["host"]}


def card_data(meta: dict[str, Any], text: str) -> dict[str, Any]:
    """`file_card` data of a page; `source_url` makes the card show [Otevrit original] instead of a download button.
    Everything here is untrusted page text: the browser puts it in with textContent only."""
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(meta["fetched_at"]))
    shown = {"host": meta["host"], "fetched": when, "fetches": meta["fetch_count"], "lang": meta["lang"],
             "author": meta["author"], "published": meta["published"]}
    summary = meta["description"] or " ".join(text.split())
    return {
        "id": meta["id"], "web_id": meta["id"], "name": meta["host"], "kind": "web", "size": meta["bytes"],
        "title": meta["title"], "summary": summary[:SUMMARY_CHARS], "meta": {k: v for k, v in shown.items() if v},
        "outline": meta["outline"][:CARD_OUTLINE], "text_excerpt": text[:EXCERPT_CHARS],
        "truncated": meta["truncated"] or len(text) > EXCERPT_CHARS, "source_url": meta["url"],
    }
