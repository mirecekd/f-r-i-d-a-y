# backend/app/webpages/meta.py
"""Page metadata from <title>, <meta>, <link rel=canonical> and JSON-LD Article blocks (OpenGraph first)."""

import json
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

ARTICLE_TYPES = {"article", "newsarticle", "blogposting", "report", "scholarlyarticle", "techarticle", "webpage"}
MAX_LD_CHARS = 200_000


class _Head(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title = ""
        self.canonical = ""
        self.lang = ""
        self.ld: list[str] = []
        self._in_title = False
        self._in_ld = False
        self._ld_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html" and a.get("lang"):
            self.lang = a["lang"]
        elif tag == "title" and not self.title:
            self._in_title = True
        elif tag == "meta":
            key = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
            if key and a.get("content") and key not in self.meta:
                self.meta[key] = a["content"].strip()
        elif tag == "link" and "canonical" in a.get("rel", "").lower().split() and a.get("href") and not self.canonical:
            self.canonical = a["href"].strip()
        elif tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self._in_ld, self._ld_buf = True, []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "script" and self._in_ld:
            self._in_ld = False
            self.ld.append("".join(self._ld_buf)[:MAX_LD_CHARS])

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif self._in_ld:
            self._ld_buf.append(data)


def _nodes(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [n for v in value for n in _nodes(v)]
    if isinstance(value, dict):
        return [value, *_nodes(value.get("@graph", []))]
    return []


def _name(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(n for n in (_name(v) for v in value[:5]) if n)
    if isinstance(value, dict):
        return _name(value.get("name"))
    return " ".join(str(value).split()) if isinstance(value, str) else ""


def _article_ld(blocks: list[str]) -> dict[str, Any]:
    for raw in blocks:
        try:
            nodes = _nodes(json.loads(raw))
        except ValueError:
            continue
        for node in nodes:
            types = node.get("@type")
            kinds = {str(t).lower() for t in (types if isinstance(types, list) else [types])}
            if kinds & ARTICLE_TYPES:
                return node
    return {}


def _clean(text: str, limit: int) -> str:
    return " ".join(text.split())[:limit]


def page_meta(html: str, url: str) -> dict[str, str]:
    """title, canonical, site, author, published, description, lang, image: all strings, '' when unknown."""
    head = _Head()
    head.feed(html)
    head.close()
    m, ld = head.meta, _article_ld(head.ld)
    image = (
        m.get("og:image")
        or m.get("twitter:image")
        or _name(ld.get("image"))
        or (str(ld["image"].get("url", "")) if isinstance(ld.get("image"), dict) else "")
    )
    if isinstance(ld.get("image"), str):
        image = image or ld["image"]
    canonical = head.canonical or m.get("og:url", "")
    return {
        "title": _clean(
            m.get("og:title") or _name(ld.get("headline")) or head.title or m.get("twitter:title", ""), 200
        ),
        "canonical": urljoin(url, canonical)[:2048] if canonical else "",
        "site": _clean(m.get("og:site_name") or _name(ld.get("publisher")), 100),
        "author": _clean(m.get("author") or m.get("article:author") or _name(ld.get("author")), 120),
        "published": _clean(m.get("article:published_time") or m.get("date") or str(ld.get("datePublished") or ""), 40),
        "description": _clean(m.get("og:description") or m.get("description") or str(ld.get("description") or ""), 400),
        "lang": _clean((head.lang or m.get("og:locale", "")).replace("_", "-"), 12),
        "image": urljoin(url, image)[:2048] if image else "",
    }
