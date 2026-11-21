# backend/app/files/common.py
"""Limits and helpers shared by the file extractors. Extracted text is always untrusted data."""

import re
from typing import Any

MAX_BYTES = 25 * 1024 * 1024  # decoded upload
MAX_TEXT = 200_000  # characters kept per file
TABLE_ROWS, TABLE_COLS, CELL_CHARS = 200, 30, 200
MAX_ZIP_ENTRIES = 5000
MAX_ZIP_UNPACKED = 200 * 1024 * 1024
MAX_MEMBER = 20 * 1024 * 1024
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class ExtractError(ValueError):
    """The file cannot be read as its kind; the message is safe to show to the user."""


def clean(text: str) -> str:
    """Normalise newlines and drop control characters (keeps tab and newline)."""
    return _CONTROL.sub("", text.replace("\r\n", "\n").replace("\r", "\n"))


def cap(text: str) -> tuple[str, bool]:
    return (text[:MAX_TEXT], True) if len(text) > MAX_TEXT else (text, False)


def cell(value: Any) -> str:
    text = "" if value is None else clean(str(value))
    return text if len(text) <= CELL_CHARS else text[: CELL_CHARS - 1] + "..."


def table(name: str, rows: list[list[Any]]) -> dict[str, Any]:
    """First row is the header; rows are cut to TABLE_ROWS x TABLE_COLS of short strings."""
    used = max((i + 1 for r in rows for i, c in enumerate(r) if c not in (None, "")), default=0)
    width = min(used, TABLE_COLS)
    grid = [[cell(r[i]) if i < len(r) else "" for i in range(width)] for r in rows[: TABLE_ROWS + 1]]
    head = [h or f"col{i + 1}" for i, h in enumerate(grid[0])] if grid else []
    return {"name": name, "columns": head, "rows": grid[1:], "total_rows": max(len(rows) - 1, 0)}


def result(kind: str, title: str, text: str, **extra: Any) -> dict[str, Any]:
    body, truncated = cap(clean(text))
    out: dict[str, Any] = {"kind": kind, "title": title[:200], "text": body, "truncated": truncated,
                           "meta": {}, "tables": [], "outline": []}
    out.update(extra)
    return out
