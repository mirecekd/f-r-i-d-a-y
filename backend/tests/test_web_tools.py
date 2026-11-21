# backend/tests/test_web_tools.py
"""Web page tools and the web_add message, with a fake fetcher (no network)."""

import asyncio
from typing import Any

from web_fixtures import ARTICLE

from app.deck import query
from app.deck.session import DeckSession
from app.scene import SceneStore
from app.tools_friday.ctx import Ctx
from app.voice.tools import ToolRegistry
from app.webpages import fetch as web_fetch
from app.webpages import tools as web_tools
from app.webpages.urlguard import UrlRefused


class Sink:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def emit(self, msg: dict[str, Any]) -> None:
        self.sent.append(msg)


class Rig:
    def __init__(self, pages: dict[str, tuple[str, bytes]]) -> None:
        self.sink = Sink()
        self.ctx = Ctx(SceneStore(), self.sink.emit)
        self.deck = DeckSession(self.ctx, None, None, None)  # type: ignore[arg-type]
        self.registry = ToolRegistry({})
        self.files, self.vision = Handover(), Handover()
        self.service = web_tools.register_web_tools(self.registry, self.ctx, self.deck, self.files, self.vision)
        self.pages, self.fetched = pages, []
        self.service.fetcher = self.fetch

    async def fetch(self, url: str) -> web_fetch.Fetched:
        self.fetched.append(url)
        if url not in self.pages:
            raise UrlRefused("the server answered HTTP 404")
        ctype, body = self.pages[url]
        return web_fetch.Fetched(url, ctype, None, body, 0, "93.184.216.34")

    def call(self, name: str, **args: Any) -> dict[str, Any]:
        return asyncio.run(self.registry.tools[name].handler(args))


class Handover:
    def __init__(self) -> None:
        self.got: list[dict[str, Any]] = []

    async def on_upload(self, msg: dict[str, Any]) -> None:
        self.got.append(msg)


def article(n: int) -> bytes:
    return ARTICLE.replace(b"Soldering basics", f"Page {n}".encode()).replace(b"flux", f"flux{n}".encode())


def test_tools_are_registered_with_long_flags():
    rig = Rig({})
    t = rig.registry.tools
    assert set(t) == {"web_add", "web_refresh", "web_read", "web_compare"}
    assert t["web_add"].long and t["web_add"].scheduling == "WHEN_IDLE" and not t["web_read"].long


def test_web_add_stores_registers_and_places_the_entity():
    rig = Rig({"https://example.org/a": ("text/html", ARTICLE)})
    out = rig.call("web_add", url="https://example.org/a")
    assert out["ok"] and out["placed"] and out["title"] == "Soldering basics"
    ents = [o for o in rig.ctx.scene.objects() if o["kind"] == "entity"]
    assert len(ents) == 1 and ents[0]["ref"] == {"type": "web", "id": out["web_id"]} and ents[0]["shape"] == "doc"
    assert query.get(out["id"]) is not None
    again = rig.call("web_add", url="https://example.org/a")
    assert again["fetch_count"] == 2 and len([o for o in rig.ctx.scene.objects() if o["kind"] == "entity"]) == 1
    assert query.count_items("web", None) == 1


def test_web_add_place_false_and_refusal_message():
    rig = Rig({"https://example.org/a": ("text/html", ARTICLE)})
    assert "placed" not in rig.call("web_add", url="https://example.org/a", place=False)
    assert rig.ctx.scene.objects() == []
    err = rig.call("web_add", url="https://example.org/missing")
    assert "cannot add the page" in err["error"] and "404" in err["error"]


def test_web_add_message_reports_error_to_the_browser():
    rig = Rig({})
    asyncio.run(rig.service.on_message({"t": "web_add", "url": "http://127.0.0.1:8670/health"}))
    assert rig.sink.sent[-1]["t"] == "error" and "cannot add the page" in rig.sink.sent[-1]["message"]
    assert rig.fetched == [] or rig.fetched == ["http://127.0.0.1:8670/health"]  # the fake is never a real network


def test_pdf_and_image_go_to_the_existing_pipelines():
    rig = Rig({"https://example.org/x.pdf": ("application/pdf", b"%PDF-1"), "https://example.org/p.png": ("image/png", b"\x89PNG")})
    assert rig.call("web_add", url="https://example.org/x.pdf")["handed_to"] == "files"
    assert rig.call("web_add", url="https://example.org/p.png")["handed_to"] == "vision"
    assert rig.files.got[0]["t"] == "file_upload" and rig.files.got[0]["name"] == "x.pdf"
    assert rig.vision.got[0]["t"] == "image_upload" and query.count_items("web", None) == 0


def test_web_read_pages_and_wraps_untrusted_text(monkeypatch):
    monkeypatch.setattr(web_tools, "PAGE_CHARS", 300)
    rig = Rig({"https://example.org/a": ("text/html", ARTICLE)})
    added = rig.call("web_add", url="https://example.org/a")
    first = rig.call("web_read", deck_id=added["id"])
    assert first["ok"] and first["parts"] >= 2 and first["content"].startswith("<web-content") and "untrusted" in first
    assert rig.call("web_read", deck_id=added["id"], part=2)["part"] == 2
    assert "does not exist" in rig.call("web_read", deck_id=added["id"], part=99)["error"]
    assert "positive integer" in rig.call("web_read", deck_id=added["id"], part="x")["error"]
    assert "unknown web page" in rig.call("web_read", deck_id="nope")["error"]


def test_web_refresh_fetches_again_without_placing():
    rig = Rig({"https://example.org/a": ("text/html", ARTICLE)})
    added = rig.call("web_add", url="https://example.org/a", place=False)
    out = rig.call("web_refresh", deck_id=added["id"])
    assert out["ok"] and out["fetch_count"] == 2 and "placed" not in out
    assert "unknown web page" in rig.call("web_refresh", deck_id="zzzz")["error"]


def test_web_compare_trims_to_budget_and_validates(monkeypatch):
    monkeypatch.setattr(web_tools, "COMPARE_BUDGET", 400)
    rig = Rig({f"https://example.org/{n}": ("text/html", article(n)) for n in (1, 2)})
    ids = [rig.call("web_add", url=f"https://example.org/{n}", place=False)["id"] for n in (1, 2)]
    out = rig.call("web_compare", ids=ids)
    assert out["ok"] and len(out["pages"]) == 2 and all(p["cut"] for p in out["pages"])
    assert all(len(p["content"]) < 400 + 200 for p in out["pages"]) and "untrusted" in out
    assert "2 to 6" in rig.call("web_compare", ids=ids[:1])["error"]
    assert "unknown web page" in rig.call("web_compare", ids=[ids[0], "nope"])["error"]
