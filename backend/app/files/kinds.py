# backend/app/files/kinds.py
"""Decide what an upload really is from magic bytes, archive contents and the extension; the mime is ignored."""

import io
import zipfile
from pathlib import PurePosixPath

from app.vision.images import sniff_mime

CODE_EXT = {
    "py", "js", "mjs", "ts", "jsx", "tsx", "c", "h", "cpp", "hpp", "cc", "cs", "java", "kt", "go", "rs", "rb", "php",
    "sh", "bash", "zsh", "ps1", "sql", "swift", "lua", "r", "pl", "scala", "css", "scss", "vue", "svelte", "dart",
    "ini", "cfg", "conf", "gradle", "cmake", "dockerfile", "makefile",
}
TEXT_EXT = {
    "txt": "text", "log": "text", "md": "markdown", "markdown": "markdown", "csv": "csv", "tsv": "csv",
    "json": "json", "jsonl": "json", "yaml": "yaml", "yml": "yaml", "toml": "toml", "xml": "xml", "svg": "xml",
    "html": "html", "htm": "html", "xhtml": "html", "rtf": "rtf",
}
AUDIO_EXT = {"mp3", "wav", "flac", "ogg", "oga", "opus", "m4a", "aac", "wma"}
VIDEO_EXT = {"mp4", "mov", "mkv", "webm", "avi", "m4v", "wmv"}
OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def ext_of(name: str) -> str:
    base = PurePosixPath(name.replace("\\", "/")).name.lower()
    return base.rsplit(".", 1)[1] if "." in base else base


def looks_text(raw: bytes) -> bool:
    head = raw[:8192]
    if head.startswith((b"\xff\xfe", b"\xfe\xff", b"\xef\xbb\xbf")):
        return True
    if b"\x00" in head:
        return False
    odd = sum(1 for b in head if b < 9 or 13 < b < 32)
    return odd * 20 <= max(len(head), 1)


def _zip_kind(raw: bytes) -> str:
    try:
        names = set(zipfile.ZipFile(io.BytesIO(raw)).namelist())
    except (zipfile.BadZipFile, OSError, ValueError):
        return "binary"
    if "word/document.xml" in names:
        return "docx"
    if "xl/workbook.xml" in names:
        return "xlsx"
    if "META-INF/container.xml" in names and "mimetype" in names:
        return "epub"
    if "content.xml" in names and "mimetype" in names:
        return "odt"
    return "zip"


def _media(raw: bytes, ext: str) -> str | None:
    head = raw[:16]
    if head.startswith((b"ID3", b"\xff\xfb", b"\xff\xf3", b"fLaC", b"OggS")) or (head[:4] == b"RIFF" and head[8:12] == b"WAVE"):
        return "audio"
    if head[4:8] == b"ftyp":
        return "audio" if raw[8:12] == b"M4A " or ext in AUDIO_EXT else "video"
    if head.startswith(b"\x1a\x45\xdf\xa3") or (head[:4] == b"RIFF" and head[8:12] == b"AVI "):
        return "video"
    return None


def detect(raw: bytes, name: str) -> tuple[str, str | None]:
    """(kind, note). The note says when the name or extension contradicts the content."""
    ext = ext_of(name)
    if sniff_mime(raw):
        return "image", None
    if b"%PDF-" in raw[:1024]:
        return "pdf", None
    if raw.startswith((b"PK\x03\x04", b"PK\x05\x06")):
        return _zip_kind(raw), None
    if raw.startswith(OLE):
        return "binary", "legacy Office binary format (doc/xls/ppt) is not supported; save as docx or xlsx"
    media = _media(raw, ext)
    if media:
        return media, None
    if raw.startswith(b"{\\rtf"):
        return "rtf", None
    if not raw:
        return "text", None
    if looks_text(raw):
        if ext in ("pdf", "docx", "xlsx", "epub", "odt", "zip"):
            return "text", f"named .{ext} but the content is plain text"
        kind = TEXT_EXT.get(ext) or ("code" if ext in CODE_EXT else "text")
        if kind == "text" and raw.lstrip()[:15].lower().startswith((b"<!doctype html", b"<html")):
            kind = "html"
        return ("text" if kind == "rtf" else kind), None
    if ext in AUDIO_EXT:
        return "audio", None
    if ext in VIDEO_EXT:
        return "video", None
    if ext in ("pdf", "docx", "xlsx", "epub", "odt", "zip"):
        return "binary", f"named .{ext} but the content is not a valid {ext} file"
    return "binary", None
