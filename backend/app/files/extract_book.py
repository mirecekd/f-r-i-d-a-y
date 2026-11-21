# backend/app/files/extract_book.py
"""Extractors for epub, odt and zip listings (zip based, bounded reads, XML through defusedxml)."""

import posixpath
from typing import Any

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

from app.files.common import ExtractError, result
from app.files.htmltext import html_to_text
from app.files.textdecode import decode_text
from app.files.ziputil import open_zip, read_member

MAX_CHAPTERS = 300


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse(data: bytes) -> Any:
    try:
        return SafeET.fromstring(data)
    except (SafeET.ParseError, DefusedXmlException, ValueError) as e:
        raise ExtractError("the package XML is malformed or uses forbidden entities") from e


def extract_epub(raw: bytes) -> dict[str, Any]:
    zf = open_zip(raw)
    container = _parse(read_member(zf, "META-INF/container.xml"))
    root_file = next((e.get("full-path") for e in container.iter() if _local(e.tag) == "rootfile"), None)
    if not root_file:
        raise ExtractError("the EPUB has no package document")
    opf = _parse(read_member(zf, root_file))
    base = posixpath.dirname(root_file)
    title = next((e.text.strip() for e in opf.iter() if _local(e.tag) == "title" and e.text), "EPUB book")
    manifest = {e.get("id"): e.get("href") for e in opf.iter() if _local(e.tag) == "item"}
    spine = [e.get("idref") for e in opf.iter() if _local(e.tag) == "itemref"][:MAX_CHAPTERS]
    names = set(zf.namelist())
    parts, outline = [], []
    for ref in spine:
        href = manifest.get(ref)
        path = posixpath.normpath(posixpath.join(base, href.split("#")[0])) if href else ""
        if path not in names:
            continue
        text, ctitle, heads = html_to_text(decode_text(read_member(zf, path))[0])
        if text:
            parts.append(text)
            outline.append((heads[0] if heads else ctitle) or posixpath.basename(path))
        if sum(len(p) for p in parts) > 250_000:
            break
    out = result("epub", title, "\n\n".join(parts), outline=outline[:60])
    out["meta"] = {"chapters": len(spine), "chapters_read": len(parts)}
    return out


def extract_odt(raw: bytes) -> dict[str, Any]:
    zf = open_zip(raw)
    root = _parse(read_member(zf, "content.xml"))
    lines, outline = [], []
    for e in root.iter():
        if _local(e.tag) in ("p", "h"):
            text = "".join(e.itertext()).strip()
            if text:
                lines.append(text)
                if _local(e.tag) == "h":
                    outline.append(text[:120])
    return result("odt", outline[0] if outline else "OpenDocument text", "\n".join(lines), outline=outline[:60])


def extract_zip(raw: bytes) -> dict[str, Any]:
    zf = open_zip(raw)
    entries = [{"name": i.filename[:200], "size": i.file_size, "dir": i.is_dir()} for i in zf.infolist()]
    listing = "\n".join(f"{'d' if e['dir'] else '-'} {e['size']:>10}  {e['name']}" for e in entries)
    out = result("zip", "Zip archive", listing)
    out["meta"] = {"entries": len(entries), "unpacked_bytes": sum(e["size"] for e in entries), "listing_only": True}
    out["outline"] = [e["name"] for e in entries[:60]]
    return out
