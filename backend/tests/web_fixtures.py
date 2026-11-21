# backend/tests/web_fixtures.py
"""Page fixtures and the extraction dict the store tests start from."""

from app.webpages.extract import extract_html

ARTICLE = (
    b"<html lang='en'><head><title>Soldering basics</title><meta property='og:site_name' content='Maker Notes'>"
    b"<meta name='description' content='How to solder.'></head><body><nav>Home About</nav><article><h1>Soldering basics</h1>"
    b"<p>" + b"Use flux and a clean tip. " * 20 + b"</p><h2>Tips</h2><p>Heat the pad first, then feed the solder.</p>"
    b"</article><footer>copyright</footer></body></html>"
)


def article_extract(raw: bytes = ARTICLE, url: str = "https://example.org/solder"):
    return extract_html(raw, url)
