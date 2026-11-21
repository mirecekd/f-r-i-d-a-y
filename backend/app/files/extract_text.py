# backend/app/files/extract_text.py
"""Extractors for text like files (txt, md, log, code, json, yaml, toml, xml, html, csv, rtf) and for media/binary."""

import csv
import io
import json
import re
from typing import Any

from app.files.common import ExtractError, result, table
from app.files.htmltext import html_to_text
from app.files.textdecode import decode_text

_MD_HEAD = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$", re.M)
_RTF_CTRL = re.compile(r"\\'([0-9a-f]{2})|\\[a-z]+-?\d* ?|[{}]", re.I)


def extract_plain(raw: bytes, kind: str, name: str) -> dict[str, Any]:
    text, enc = decode_text(raw)
    outline = [m.group(2)[:120] for m in _MD_HEAD.finditer(text)][:60] if kind == "markdown" else []
    out = result(kind, name or "Text file", text, outline=outline)
    out["meta"] = {"encoding": enc, "lines": text.count("\n") + 1}
    if kind == "json":
        try:
            parsed = json.loads(text)
        except ValueError:
            out["meta"]["valid"] = False
        else:
            out["meta"]["valid"] = True
            out["meta"]["top_level"] = type(parsed).__name__
    return out


def extract_html(raw: bytes, name: str) -> dict[str, Any]:
    text, enc = decode_text(raw)
    plain, title, heads = html_to_text(text)
    out = result("html", title or name or "HTML page", plain, outline=heads)
    out["meta"] = {"encoding": enc, "text_only": True}
    return out


def extract_csv(raw: bytes, name: str) -> dict[str, Any]:
    text, enc = decode_text(raw)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel_tab if name.lower().endswith(".tsv") else csv.excel
    rows: list[list[str]] = []
    csv.field_size_limit(1_000_000)
    try:
        for i, row in enumerate(csv.reader(io.StringIO(text, newline=""), dialect)):
            rows.append(row)
            if i >= 5000:
                break
    except csv.Error as e:
        raise ExtractError(f"the CSV cannot be parsed ({e})") from e
    total = text.count("\n")
    out = result("csv", name or "Table", text, tables=[table(name or "data", rows)])
    out["meta"] = {"encoding": enc, "delimiter": dialect.delimiter, "rows": total, "columns": max((len(r) for r in rows), default=0)}
    return out


def extract_rtf(raw: bytes, name: str) -> dict[str, Any]:
    text, _ = decode_text(raw)
    plain = _RTF_CTRL.sub(lambda m: chr(int(m.group(1), 16)) if m.group(1) else "", text)
    return result("rtf", name or "RTF document", plain)


def extract_media(raw: bytes, kind: str, name: str) -> dict[str, Any]:
    out = result(kind, name or kind, f"{kind.capitalize()} file, {len(raw)} bytes. Transcription is not available yet.")
    out["meta"] = {"bytes": len(raw), "transcription": "not available yet"}
    return out


def extract_binary(raw: bytes, name: str) -> dict[str, Any]:
    head = raw[:256]
    rows = []
    for i in range(0, len(head), 16):
        chunk = head[i : i + 16]
        rows.append(f"{i:04x}  {chunk.hex(' '):<47}  {''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)}")
    out = result("binary", name or "Binary file", f"Unknown binary file, {len(raw)} bytes. First bytes:\n" + "\n".join(rows))
    out["meta"] = {"bytes": len(raw), "magic": head[:8].hex()}
    return out
