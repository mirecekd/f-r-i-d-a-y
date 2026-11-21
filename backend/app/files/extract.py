# backend/app/files/extract.py
"""Entry point: bytes + file name -> {kind, title, text, truncated, meta, tables, outline, note?}."""

from typing import Any

from app.files import extract_book, extract_office, extract_text
from app.files.common import MAX_BYTES, ExtractError
from app.files.kinds import detect


def extract(raw: bytes, name: str) -> dict[str, Any]:
    """Detect the kind from the content and extract it; raises ExtractError for oversize or unreadable files."""
    if len(raw) > MAX_BYTES:
        raise ExtractError(f"file is larger than {MAX_BYTES // (1024 * 1024)} MB")
    kind, note = detect(raw, name)
    try:
        out = _dispatch(kind, raw, name)
    except ExtractError as e:
        if kind in ("pdf", "docx", "xlsx", "epub", "odt", "zip"):
            out = extract_text.extract_binary(raw, name)  # keep the file, tell the model why it is unreadable
            out["note"] = str(e)
            out["kind"] = kind
            return out
        raise
    if note:
        out["note"] = note
    return out


def _dispatch(kind: str, raw: bytes, name: str) -> dict[str, Any]:
    if kind == "pdf":
        return extract_office.extract_pdf(raw)
    if kind == "docx":
        return extract_office.extract_docx(raw)
    if kind == "xlsx":
        return extract_office.extract_xlsx(raw)
    if kind == "epub":
        return extract_book.extract_epub(raw)
    if kind == "odt":
        return extract_book.extract_odt(raw)
    if kind == "zip":
        return extract_book.extract_zip(raw)
    if kind == "csv":
        return extract_text.extract_csv(raw, name)
    if kind == "html":
        return extract_text.extract_html(raw, name)
    if kind == "rtf":
        return extract_text.extract_rtf(raw, name)
    if kind in ("audio", "video"):
        return extract_text.extract_media(raw, kind, name)
    if kind == "binary":
        return extract_text.extract_binary(raw, name)
    return extract_text.extract_plain(raw, kind, name)
