# backend/app/files/extract_office.py
"""Extractors for pdf, docx, xlsx: pure functions bytes -> result dict. No macros, no external fetches."""

import io
from typing import Any

from app.files.common import MAX_TEXT, TABLE_COLS, TABLE_ROWS, ExtractError, clean, result, table
from app.files.ziputil import open_zip

MAX_PDF_PAGES = 400
MAX_SHEETS = 20


def extract_pdf(raw: bytes) -> dict[str, Any]:
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    try:
        reader = PdfReader(io.BytesIO(raw))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ExtractError("the PDF is password protected")
        pages, size, parts = len(reader.pages), 0, []
        for page in reader.pages[:MAX_PDF_PAGES]:
            text = clean(page.extract_text() or "")
            parts.append(text)
            size += len(text)
            if size > MAX_TEXT:
                break
        meta = reader.metadata
        title = str(meta.title) if meta and meta.title else ""
        outline = [str(getattr(o, "title", "")) for o in reader.outline if not isinstance(o, list)][:60]
    except ExtractError:
        raise
    except (PyPdfError, ValueError, KeyError, TypeError, AttributeError, RecursionError, OSError) as e:
        raise ExtractError(f"the PDF cannot be read ({type(e).__name__})") from e
    body = "\n\n".join(f"[page {i + 1}]\n{t}" for i, t in enumerate(parts))
    out = result("pdf", title or "PDF document", body, outline=outline)
    out["meta"] = {"pages": pages, "pages_read": len(parts), "scanned_hint": pages > 0 and size < 20 * len(parts)}
    out["truncated"] = out["truncated"] or len(parts) < pages
    return out


def extract_docx(raw: bytes) -> dict[str, Any]:
    from docx import Document

    open_zip(raw)  # bomb guard before python-docx touches the archive
    try:
        doc = Document(io.BytesIO(raw))
    except Exception as e:  # python-docx raises KeyError, BadZipFile, lxml errors, ...
        raise ExtractError(f"the document cannot be read ({type(e).__name__})") from e
    lines: list[str] = []
    outline: list[str] = []
    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        style = (p.style.name if p.style is not None and p.style.name else "")
        if style.startswith("Heading") or style == "Title":
            level = int(style[8:]) if style[8:].isdigit() else 1
            lines.append("#" * min(level, 6) + " " + text)
            outline.append(text[:120])
        else:
            lines.append(text)
    tables = []
    for i, t in enumerate(doc.tables[:20]):
        rows = [[c.text for c in r.cells] for r in t.rows[: TABLE_ROWS + 1]]
        tables.append(table(f"Table {i + 1}", rows))
        lines.append(f"[table {i + 1}: {len(t.rows)} rows]\n" + "\n".join(" | ".join(r) for r in rows[:50]))
    title = (doc.core_properties.title or "").strip() or (outline[0] if outline else "Word document")
    out = result("docx", title, "\n\n".join(lines), outline=outline[:60], tables=tables)
    out["meta"] = {"paragraphs": len(doc.paragraphs), "tables": len(doc.tables)}
    return out


def extract_xlsx(raw: bytes) -> dict[str, Any]:
    from openpyxl import load_workbook

    open_zip(raw)
    try:
        wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    except Exception as e:  # openpyxl raises many types for damaged workbooks
        raise ExtractError(f"the workbook cannot be read ({type(e).__name__})") from e
    tables, lines, sheets = [], [], []
    try:
        for ws in wb.worksheets[:MAX_SHEETS]:
            rows: list[list[Any]] = []
            for row in ws.iter_rows(max_row=TABLE_ROWS * 5, max_col=TABLE_COLS, values_only=True):
                rows.append(list(row))
            while rows and not any(c not in (None, "") for c in rows[-1]):
                rows.pop()
            sheets.append({"name": ws.title, "rows": ws.max_row, "cols": ws.max_column})
            tables.append(table(ws.title, rows))
            lines.append(f"## {ws.title}\n" + "\n".join(" | ".join("" if c is None else str(c) for c in r) for r in rows))
    finally:
        wb.close()
    out = result("xlsx", "Spreadsheet", "\n\n".join(lines), tables=tables, outline=[s["name"] for s in sheets])
    out["meta"] = {"sheets": sheets}
    return out
