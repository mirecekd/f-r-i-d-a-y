# backend/app/webpages/readable.py
"""Readability-style main text of an HTML page with the stdlib parser: static HTML only, scripts are never run."""

from html.parser import HTMLParser
from urllib.parse import urljoin

DROP = {
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "iframe",
    "canvas",
    "nav",
    "footer",
    "aside",
    "form",
    "select",
    "button",
    "dialog",
    "head",
}
VOID = {"br", "hr", "img", "input", "meta", "link", "source", "wbr", "area", "base", "col", "embed", "track", "param"}
BLOCK = {
    "p",
    "div",
    "section",
    "article",
    "main",
    "header",
    "blockquote",
    "pre",
    "figure",
    "figcaption",
    "dl",
    "dt",
    "dd",
    "ul",
    "ol",
    "table",
    "caption",
    "tr",
    "address",
    "details",
    "summary",
}
MAX_LINKS = 50
MIN_PREFERRED_CHARS = 200


class _Buffer:
    def __init__(self) -> None:
        self.parts: list[str] = []
        self.headings: list[str] = []

    def text(self) -> str:
        lines = [" ".join(line.split()) for line in "".join(self.parts).split("\n")]
        out: list[str] = []
        for line in lines:
            if line or (out and out[-1]):
                out.append(line)
        return "\n".join(out).strip()


class _Reader(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.everything, self.article, self.main = _Buffer(), _Buffer(), _Buffer()
        self.links = 0
        self._skip = 0
        self._article = 0
        self._main = 0
        self._heading: tuple[int, list[str]] | None = None
        self._link: tuple[str, list[str]] | None = None
        self._lists: list[str] = []

    def _active(self) -> list[_Buffer]:
        return [self.everything, *([self.article] if self._article else []), *([self.main] if self._main else [])]

    def _emit(self, text: str) -> None:
        if self._link is not None:
            self._link[1].append(text)
        else:
            self._write(text)

    def _write(self, text: str) -> None:
        for buf in self._active():
            buf.parts.append(text)
        if self._heading is not None:
            self._heading[1].append(text)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._skip:
            if tag in DROP and tag not in VOID:
                self._skip += 1
            return
        if tag in DROP:
            self._skip = 1
            return
        if tag == "article":
            self._article += 1
        elif tag == "main":
            self._main += 1
        if tag in ("ul", "ol"):
            self._lists.append(tag)
        if len(tag) == 2 and tag[0] == "h" and tag[1] in "123456":
            self._write("\n\n" + "#" * int(tag[1]) + " ")
            self._heading = (int(tag[1]), [])
        elif tag == "li":
            self._write("\n" + ("- " if not self._lists or self._lists[-1] == "ul" else "* "))
        elif tag in ("td", "th"):
            self._write(" | ")
        elif tag in ("br", "hr"):
            self._write("\n")
        elif tag == "pre":
            self._write("\n\n")
        elif tag in BLOCK:
            self._write("\n\n" if tag in ("p", "blockquote", "table", "section", "article") else "\n")
        elif tag == "a" and self._link is None:
            href = dict(attrs).get("href") or ""
            absolute = urljoin(self.base_url, href) if href else ""
            self._link = (absolute if absolute.startswith(("http://", "https://")) else "", [])
        elif tag == "img":
            alt = " ".join((dict(attrs).get("alt") or "").split())
            if alt:
                self._emit(f"[image: {alt[:120]}]")

    def handle_endtag(self, tag: str) -> None:
        if self._skip:
            if tag in DROP:
                self._skip -= 1
            return
        if tag == "article" and self._article:
            self._article -= 1
        elif tag == "main" and self._main:
            self._main -= 1
        elif tag in ("ul", "ol") and self._lists:
            self._lists.pop()
            self._write("\n")
        elif len(tag) == 2 and tag[0] == "h" and tag[1] in "123456" and self._heading is not None:
            text = " ".join("".join(self._heading[1]).split())
            if text and self._heading[0] <= 3:
                for buf in self._active():
                    buf.headings.append(text[:120])
            self._heading = None
            self._write("\n\n")
        elif tag == "a" and self._link is not None:
            href, pieces = self._link
            self._link = None
            label = " ".join("".join(pieces).split())
            if label and href and self.links < MAX_LINKS:
                self.links += 1
                self._write(f"[{label}]({href})")
            else:
                self._write(label)
        elif tag in BLOCK:
            self._write("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._emit(data.replace("\n", " "))


def readable_text(html: str, base_url: str = "") -> tuple[str, list[str]]:
    """(main text, h1-h3 outline). Prefers <article>, then <main>, then the whole body minus nav/footer/aside/forms."""
    reader = _Reader(base_url)
    reader.feed(html)
    reader.close()
    for buf in (reader.article, reader.main):
        if len(buf.text()) >= MIN_PREFERRED_CHARS:
            return buf.text(), buf.headings
    return reader.everything.text(), reader.everything.headings
