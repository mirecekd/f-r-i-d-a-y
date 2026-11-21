# backend/app/webpages/extract.py
"""Pure functions: HTML bytes to {title, text, outline, ...}. Everything in the result is UNTRUSTED data."""

import re
from typing import Any

from app.files.textdecode import decode_text
from app.webpages.meta import page_meta
from app.webpages.readable import readable_text

MAX_TEXT = 200_000
_CHARSET = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?\s*([A-Za-z0-9_.:-]+)""", re.I)
_CZECH = set("ěščřžťďňůĚŠČŘŽŤĎŇŮ")
STOP = {
    "en": {"the", "and", "of", "to", "is", "in", "that", "for", "with", "this"},
    "cs": {"a", "je", "se", "na", "že", "to", "v", "s", "pro", "který", "jsou"},
    "de": {"der", "die", "und", "das", "ist", "nicht", "mit", "ein", "den"},
    "fr": {"le", "la", "les", "et", "des", "est", "une", "pour", "que"},
    "es": {"el", "los", "las", "y", "es", "una", "por", "con", "que"},
}


def decode_html(raw: bytes, header_charset: str | None) -> str:
    """The HTTP charset, else a <meta charset>, else the shared utf-8 / cp1250 / latin-1 detection."""
    for name in (
        header_charset,
        (m.group(1).decode("ascii", "ignore") if (m := _CHARSET.search(raw[:4096])) else None),
    ):
        if name:
            try:
                return raw.decode(name.strip(), errors="replace")
            except LookupError:
                continue
    return decode_text(raw)[0]


def guess_language(text: str, declared: str = "") -> str:
    """The declared lang attribute when it looks right, else a stop-word guess among en/cs/de/fr/es ('' when unsure)."""
    if re.fullmatch(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*", declared or ""):
        return declared.split("-")[0].lower()
    words = re.findall(r"[^\W\d_]+", text[:20_000].lower())
    if len(words) < 20:
        return ""
    scores = {lang: sum(w in stop for w in words) for lang, stop in STOP.items()}
    if any(c in _CZECH for c in text[:5000]):
        scores["cs"] += len(words) // 20
    lang, best = max(scores.items(), key=lambda kv: kv[1])
    return lang if best >= max(3, len(words) // 25) else ""


def extract_html(raw: bytes, url: str, charset: str | None = None) -> dict[str, Any]:
    """{title, canonical, site, author, published, description, lang, image, text, outline, truncated, chars}."""
    html = decode_html(raw, charset)
    meta = page_meta(html, url)
    text, outline = readable_text(html, url)
    truncated = len(text) > MAX_TEXT
    text = text[:MAX_TEXT]
    meta["lang"] = guess_language(text, meta["lang"])
    meta["title"] = meta["title"] or (outline[0] if outline else "")
    return {**meta, "text": text, "outline": outline[:60], "truncated": truncated, "chars": len(text)}


def extract_plain(raw: bytes, charset: str | None = None) -> dict[str, Any]:
    """A text/plain response: the text itself, the first line as title."""
    text = decode_html(raw, charset) if charset else decode_text(raw)[0]
    text = text.replace("\r\n", "\n").strip()
    truncated = len(text) > MAX_TEXT
    text = text[:MAX_TEXT]
    first = next((line.strip() for line in text.split("\n") if line.strip()), "")
    return {
        "title": first[:120],
        "canonical": "",
        "site": "",
        "author": "",
        "published": "",
        "description": "",
        "lang": guess_language(text),
        "image": "",
        "text": text,
        "outline": [],
        "truncated": truncated,
        "chars": len(text),
    }
