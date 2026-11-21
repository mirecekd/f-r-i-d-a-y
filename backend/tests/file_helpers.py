# backend/tests/file_helpers.py
"""Generated test files for the file tests (all built in memory)."""

import io
import zipfile

from docx import Document
from openpyxl import Workbook
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def pdf_bytes(pages: int = 2, text: str = "Hello Friday") -> bytes:
    w = PdfWriter()
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    for n in range(pages):
        page = w.add_blank_page(200, 200)
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 20 100 Td ({text} page {n + 1}) Tj ET".encode())
        page[NameObject("/Contents")] = w._add_object(stream)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): w._add_object(font)})})
    w.add_metadata({"/Title": "Test PDF"})
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


def docx_bytes() -> bytes:
    d = Document()
    d.core_properties.title = "Report"
    d.add_heading("Intro", 1)
    d.add_paragraph("First paragraph.")
    d.add_heading("Details", 2)
    t = d.add_table(rows=2, cols=2)
    for i, v in enumerate(["Name", "Qty", "Bolt", "12"]):
        t.cell(i // 2, i % 2).text = v
    out = io.BytesIO()
    d.save(out)
    return out.getvalue()


def xlsx_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Stock"
    ws.append(["item", "qty"])
    ws.append(["bolt", 12])
    ws.append(["nut", 30])
    wb.create_sheet("Empty")
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def csv_cp1250() -> bytes:
    return "jmeno;mesto\nZdeněk;Říčany\nŽofie;Plzeň\n".encode("cp1250")


def epub_bytes() -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("META-INF/container.xml", '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                   '<rootfiles><rootfile full-path="OEBPS/c.opf"/></rootfiles></container>')
        z.writestr("OEBPS/c.opf", '<package xmlns="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/">'
                   '<metadata><dc:title>Book One</dc:title></metadata><manifest>'
                   '<item id="b" href="b.xhtml"/><item id="a" href="a.xhtml"/></manifest>'
                   '<spine><itemref idref="a"/><itemref idref="b"/></spine></package>')
        z.writestr("OEBPS/a.xhtml", "<html><body><h1>Chapter A</h1><p>Alpha text</p><script>evil()</script></body></html>")
        z.writestr("OEBPS/b.xhtml", "<html><body><h1>Chapter B</h1><p>Beta text</p></body></html>")
    return out.getvalue()


def zip_bytes() -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("a.txt", "hello")
        z.writestr("dir/b.py", "print(1)")
    return out.getvalue()


def zip_bomb() -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("zeros.bin", b"\0" * (30 * 1024 * 1024))
    return out.getvalue()
