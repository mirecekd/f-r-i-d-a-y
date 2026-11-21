# backend/tests/test_web_limits.py
"""Limits of the page fetcher: redirect count, content type, body size, error statuses, switches, ports, request headers."""

import asyncio

import pytest
from web_helpers import PUBLIC_IP, FakeNet, http_answer, redirect, resolver

from app.webpages import fetch as web_fetch
from app.webpages.urlguard import UrlRefused, ip_refusal


def test_more_than_five_redirects_is_refused():
    net = FakeNet([redirect("https://ok.example/n")] * 8)
    with pytest.raises(UrlRefused, match="more than 5 redirects"):
        asyncio.run(web_fetch.fetch("https://ok.example/", resolver=resolver({"ok.example": [PUBLIC_IP]}), backend=net.factory))
    assert len(net.connects) == 6


def test_five_redirects_are_followed():
    net = FakeNet([redirect("/a")] * 5 + [http_answer(body=b"<p>end</p>")])
    got = asyncio.run(web_fetch.fetch("https://ok.example/", resolver=resolver({"ok.example": [PUBLIC_IP]}), backend=net.factory))
    assert got.redirects == 5 and got.url == "https://ok.example/a"


@pytest.mark.parametrize("ctype", ["application/zip", "application/octet-stream", "text/javascript", "application/json", "video/mp4", None])
def test_wrong_content_type_is_refused(ctype):
    net = FakeNet([http_answer(ctype=ctype)])
    with pytest.raises(UrlRefused, match="not supported"):
        asyncio.run(web_fetch.fetch("https://ok.example/", resolver=resolver({"ok.example": [PUBLIC_IP]}), backend=net.factory))


def test_oversized_body_is_refused_by_header_and_while_streaming():
    big = b"x" * (web_fetch.MAX_BYTES + 10)
    for answer in (http_answer(body=big), http_answer(body=big, length=False)):
        net = FakeNet([answer])
        with pytest.raises(UrlRefused, match="larger than 5 MB"):
            asyncio.run(web_fetch.fetch("https://ok.example/", resolver=resolver({"ok.example": [PUBLIC_IP]}), backend=net.factory))


def test_http_error_and_compressed_answers_are_refused():
    for answer, match in ((http_answer(404), "HTTP 404"), (http_answer(extra={"Content-Encoding": "gzip"}), "compressed")):
        net = FakeNet([answer])
        with pytest.raises(UrlRefused, match=match):
            asyncio.run(web_fetch.fetch("https://ok.example/", resolver=resolver({"ok.example": [PUBLIC_IP]}), backend=net.factory))


def test_switch_and_lists(monkeypatch):
    net = FakeNet([http_answer()])
    res = resolver({"ok.example": [PUBLIC_IP]})
    monkeypatch.setenv("FRIDAY_WEB_DENYLIST", "ok.example")
    with pytest.raises(UrlRefused, match="deny list"):
        asyncio.run(web_fetch.fetch("https://www.ok.example/", resolver=res, backend=net.factory))
    monkeypatch.delenv("FRIDAY_WEB_DENYLIST")
    monkeypatch.setenv("FRIDAY_WEB_ALLOWLIST", "other.example")
    with pytest.raises(UrlRefused, match="allow list"):
        asyncio.run(web_fetch.fetch("https://ok.example/", resolver=res, backend=net.factory))
    monkeypatch.delenv("FRIDAY_WEB_ALLOWLIST")
    monkeypatch.setenv("FRIDAY_WEB_FETCH", "0")
    with pytest.raises(UrlRefused, match="switched off"):
        asyncio.run(web_fetch.fetch("https://ok.example/", resolver=res, backend=net.factory))
    assert net.connects == []


def test_extra_ports_only_when_configured(monkeypatch):
    res = resolver({"ok.example": [PUBLIC_IP]})
    with pytest.raises(UrlRefused, match="port 8080"):
        asyncio.run(web_fetch.fetch("http://ok.example:8080/", resolver=res, backend=FakeNet([]).factory))
    monkeypatch.setenv("FRIDAY_WEB_PORTS", "8080")
    net = FakeNet([http_answer()])
    asyncio.run(web_fetch.fetch("http://ok.example:8080/", resolver=res, backend=net.factory))
    assert net.connects == [PUBLIC_IP]


def test_request_has_honest_agent_and_no_cookies():
    net = FakeNet([http_answer()])
    asyncio.run(web_fetch.fetch("https://ok.example/p?utm_source=x&a=1", resolver=resolver({"ok.example": [PUBLIC_IP]}), backend=net.factory))
    req = b"".join(net.sent).decode().lower()
    assert "user-agent: fridaybot/" in req and "cookie" not in req and "authorization" not in req
    assert "get /p?a=1 " in req  # tracking parameters are dropped


def test_ip_refusal_allows_public_addresses():
    for ip in ("93.184.216.34", "8.8.8.8", "2606:2800:220:1:248:1893:25c8:1946", "1.1.1.1"):
        assert ip_refusal(ip) is None
