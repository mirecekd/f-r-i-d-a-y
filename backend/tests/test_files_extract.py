# backend/tests/test_files_extract.py
"""Kind detection and the pure extractors, with fixtures generated in memory."""

import io
import json
import zipfile

import pytest

from app.files import common
from app.files.extract import extract
from app.files.kinds import detect
from tests.file_helpers import csv_cp1250, docx_bytes, epub_bytes, pdf_bytes, xlsx_bytes, zip_bomb, zip_bytes
from tests.vision_helpers import png_bytes


@pytest.mark.parametrize("raw,name,kind", [
    (pdf_bytes(), "a.bin", "pdf"), (docx_bytes(), "x", "docx"), (xlsx_bytes(), "x.dat", "xlsx"),
    (epub_bytes(), "b.zip", "epub"), (zip_bytes(), "a.docx", "zip"), (png_bytes(), "pic.txt", "image"),
    (b"a,b\n1,2\n", "t.csv", "csv"), (b"print(1)\n", "m.py", "code"), (b"# T\ntext", "r.md", "markdown"),
    (b"<!DOCTYPE html><p>x", "page.txt", "html"), (b'{"a": 1}', "d.json", "json"), (b"ID3\x04\x00" + b"\0" * 20, "s.mp3", "audio"),
    (b"\x00\x01\x02\xff" * 50, "blob.xyz", "binary"), (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"0" * 20, "old.doc", "binary"),
])
def test_detect_uses_content_not_the_name(raw, name, kind):
    assert detect(raw, name)[0] == kind


def test_pdf(monkeypatch):
    out = extract(pdf_bytes(3), "a.pdf")
    assert out["kind"] == "pdf" and out["title"] == "Test PDF" and out["meta"]["pages"] == 3
    assert "Hello Friday page 2" in out["text"] and "[page 3]" in out["text"] and not out["truncated"]


def test_docx_headings_and_table():
    out = extract(docx_bytes(), "r.docx")
    assert out["title"] == "Report" and out["outline"] == ["Intro", "Details"]
    assert "# Intro" in out["text"] and "## Details" in out["text"]
    assert out["tables"][0]["columns"] == ["Name", "Qty"] and out["tables"][0]["rows"] == [["Bolt", "12"]]


def test_xlsx_sheets():
    out = extract(xlsx_bytes(), "s.xlsx")
    stock = out["tables"][0]
    assert stock["name"] == "Stock" and stock["columns"] == ["item", "qty"] and stock["rows"][1] == ["nut", "30"]
    assert out["outline"] == ["Stock", "Empty"]


def test_csv_cp1250_is_decoded_and_delimiter_found():
    out = extract(csv_cp1250(), "lidi.csv")
    assert out["meta"]["encoding"] == "cp1250" and out["meta"]["delimiter"] == ";"
    assert out["tables"][0]["rows"][0] == ["Zdeněk", "Říčany"]


def test_csv_table_is_capped():
    raw = ("\n".join(",".join(str(r * c) for c in range(40)) for r in range(300))).encode()
    t = extract(raw, "big.csv")["tables"][0]
    assert len(t["rows"]) == common.TABLE_ROWS and len(t["columns"]) == common.TABLE_COLS


def test_epub_follows_the_spine_and_drops_scripts():
    out = extract(epub_bytes(), "book.epub")
    assert out["title"] == "Book One" and out["outline"] == ["Chapter A", "Chapter B"]
    assert out["text"].index("Alpha") < out["text"].index("Beta") and "evil" not in out["text"]


def test_zip_lists_entries_without_unpacking():
    out = extract(zip_bytes(), "pack.zip")
    assert out["kind"] == "zip" and out["meta"]["entries"] == 2 and out["outline"] == ["a.txt", "dir/b.py"]


def test_html_and_json():
    h = extract(b"<html><head><title>T</title><style>p{}</style></head><body><h1>Head</h1><p>Body</p><script>x()</script></body></html>", "p.html")
    assert h["title"] == "T" and h["outline"] == ["Head"] and "x()" not in h["text"] and "Body" in h["text"]
    j = extract(json.dumps({"a": [1, 2]}).encode(), "d.json")
    assert j["meta"]["valid"] and j["meta"]["top_level"] == "dict"


def test_fake_pdf_with_wrong_magic_is_not_a_pdf():
    out = extract(b"\x00\x01\x02" * 100, "evil.pdf")
    assert out["kind"] == "binary" and "not a valid pdf" in out["note"]


def test_damaged_pdf_keeps_the_file_with_a_note():
    out = extract(b"%PDF-1.4\n garbage", "broken.pdf")
    assert out["kind"] == "pdf" and "cannot be read" in out["note"]


def test_oversize_file_is_rejected():
    with pytest.raises(common.ExtractError, match="25 MB"):
        extract(b"a" * (common.MAX_BYTES + 1), "big.txt")


def test_zip_bomb_is_refused_but_kept_as_unreadable():
    out = extract(zip_bomb(), "bomb.zip")
    assert out["kind"] == "zip" and "zip bomb" in out["note"]


def test_too_many_zip_entries_are_refused():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for i in range(common.MAX_ZIP_ENTRIES + 1):
            z.writestr(f"f{i}", "")
    assert "more than" in extract(buf.getvalue(), "many.zip")["note"]


def test_control_characters_are_stripped_and_text_is_capped():
    out = extract(b"ok\x07text\x1b[31m red\r\nnext " + b"line of ordinary words " * 10, "log.txt")
    assert "\x07" not in out["text"] and "\x1b" not in out["text"] and out["text"].startswith("oktext[31m red\nnext")
    long = extract(b"x" * (common.MAX_TEXT + 50), "long.txt")
    assert len(long["text"]) == common.MAX_TEXT and long["truncated"]


def test_epub_with_entity_bomb_is_refused():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("META-INF/container.xml", '<!DOCTYPE x [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]><container>&b;</container>')
    assert "forbidden entities" in extract(buf.getvalue(), "e.epub")["note"]


def test_media_is_stored_with_a_transcription_note():
    out = extract(b"ID3\x04" + b"\0" * 30, "song.mp3")
    assert out["kind"] == "audio" and "not available yet" in out["text"]
