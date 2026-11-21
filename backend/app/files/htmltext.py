# backend/app/files/htmltext.py
"""HTML to plain text with the stdlib parser: no scripts, no styles, no fetches."""

from html.parser import HTMLParser

SKIP = {"script", "style", "head", "template", "noscript"}
BLOCK = {"p", "div", "br", "li", "tr", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "table", "ul", "ol"}
HEADINGS = {"h1", "h2", "h3"}


class _Strip(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title = ""
        self.headings: list[str] = []
        self._skip = 0
        self._in_title = False
        self._heading: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "title":
            self._in_title = True
        if tag in SKIP:
            self._skip += 1
        if tag in BLOCK:
            self.parts.append("\n")
        if tag in HEADINGS:
            self._heading = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in SKIP and self._skip:
            self._skip -= 1
        if tag in HEADINGS and self._heading is not None:
            text = " ".join("".join(self._heading).split())
            if text:
                self.headings.append(text[:120])
            self._heading = None
        if tag in BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._skip:
            return
        self.parts.append(data)
        if self._heading is not None:
            self._heading.append(data)


def html_to_text(html: str) -> tuple[str, str, list[str]]:
    """(text, title, h1-h3 headings)."""
    p = _Strip()
    p.feed(html)
    p.close()
    lines = [" ".join(line.split()) for line in "".join(p.parts).split("\n")]
    text = "\n".join(line for i, line in enumerate(lines) if line or (i and lines[i - 1]))
    return text.strip(), " ".join(p.title.split()), p.headings[:60]
