# backend/tests/test_web_ssrf.py
"""SSRF table of the page fetcher: every hostile URL is refused with a message and never reaches the network."""

import asyncio

import pytest
from web_helpers import PUBLIC_IP, FakeNet, http_answer, redirect, resolver

from app.webpages import fetch as web_fetch
from app.webpages.pinned import PinnedBackend
from app.webpages.urlguard import UrlRefused

HOSTILE = [
    "http://127.0.0.1/", "http://127.0.0.1:8670/health", "http://localhost/", "http://LOCALHOST./", "http://foo.localhost/",
    "http://0.0.0.0/", "http://[::1]/", "http://[::]/", "http://[::ffff:127.0.0.1]/", "http://[::ffff:7f00:1]/",
    "http://[fd00::1]/", "http://[fe80::1]/", "http://[64:ff9b::7f00:1]/", "http://[2002:7f00:1::]/",
    "http://169.254.169.254/latest/meta-data/", "http://[fd00:ec2::254]/", "http://10.0.0.1/", "http://10.255.255.255/",
    "http://172.16.0.1/", "http://172.31.255.254/", "http://192.168.1.1/", "http://100.64.0.1/", "http://100.127.255.254/",
    "http://224.0.0.1/", "http://255.255.255.255/", "http://192.0.0.1/", "http://198.18.0.1/",
    "http://2130706433/", "http://0x7f000001/", "http://0x7f.0.0.1/", "http://0x7f.0x0.0x0.0x1/", "http://0177.0.0.1/",
    "http://127.1/", "http://127.0.1/", "http://0/", "http://2852039166/",
    "http://a@127.0.0.1/", "http://user:pw@example.com/", "http://example.com@127.0.0.1/", "http://127.0.0.1%23@example.com/",
    "http://127.0.0.1#@example.com/", "http://127.0.0.1\\@example.com/", "http://example.com:80@127.0.0.1/",
    "file:///etc/passwd", "gopher://example.com/", "ftp://example.com/", "javascript:alert(1)", "data:text/html,hi",
    "http://example.com:22/", "http://example.com:8670/", "http://example.com:8080/", "https://example.com:6379/",
    "", "   ", "http://", "example.com", "http://exa mple.com/", "http://example.com/" + "a" * 2100,
    "http://metadata.google.internal/", "http://printer.local/", "http://nas.home.arpa/",
]


@pytest.mark.parametrize("url", HOSTILE)
def test_hostile_url_is_refused_without_network(url):
    net = FakeNet([http_answer()])
    res = resolver({})  # a name that is not an IP would fail to resolve: nothing may resolve to a public address either
    with pytest.raises(UrlRefused) as e:
        asyncio.run(web_fetch.fetch(url, resolver=res, backend=net.factory))
    assert str(e.value)
    assert net.connects == []


@pytest.mark.parametrize(
    "ip", ["10.1.1.1", "172.20.0.1", "192.168.0.9", "100.64.1.1", "127.0.0.2", "169.254.1.1", "::1", "fc00::1", "::ffff:10.0.0.1"]
)
def test_dns_name_resolving_to_private_ip_is_refused(ip):
    net = FakeNet([http_answer()])
    res = resolver({"evil.example": [ip]})
    with pytest.raises(UrlRefused, match="forbidden address"):
        asyncio.run(web_fetch.fetch("https://evil.example/", resolver=res, backend=net.factory))
    assert net.connects == []


def test_one_private_answer_among_public_ones_refuses_the_name():
    net = FakeNet([http_answer()])
    res = resolver({"mixed.example": [PUBLIC_IP, "10.0.0.5"]})
    with pytest.raises(UrlRefused):
        asyncio.run(web_fetch.fetch("https://mixed.example/", resolver=res, backend=net.factory))
    assert net.connects == []


def test_redirect_to_private_address_is_refused():
    for loc in ["http://127.0.0.1/admin", "http://169.254.169.254/", "http://[::1]/", "/\\@127.0.0.1", "gopher://x/", "file:///etc/passwd"]:
        net = FakeNet([redirect(loc), http_answer(body=b"SECRET")])
        res = resolver({"ok.example": [PUBLIC_IP]})
        with pytest.raises(UrlRefused):
            asyncio.run(web_fetch.fetch("https://ok.example/", resolver=res, backend=net.factory))
        assert net.connects == [PUBLIC_IP]  # only the first, public hop connected


def test_redirect_to_name_resolving_privately_is_refused():
    net = FakeNet([redirect("https://inner.example/x")])
    res = resolver({"ok.example": [PUBLIC_IP], "inner.example": ["192.168.1.5"]})
    with pytest.raises(UrlRefused, match="forbidden"):
        asyncio.run(web_fetch.fetch("https://ok.example/", resolver=res, backend=net.factory))
    assert net.connects == [PUBLIC_IP]


def test_dns_rebinding_connects_to_the_checked_ip_and_resolves_once_per_hop():
    answers = iter([[PUBLIC_IP], ["127.0.0.1"]])

    async def rebinding(host, port):
        return next(answers)

    net = FakeNet([http_answer(body=b"<p>ok</p>")])
    got = asyncio.run(web_fetch.fetch("https://rebind.example/", resolver=rebinding, backend=net.factory))
    assert net.connects == [PUBLIC_IP]  # the second (private) answer is never asked for
    assert got.ip == PUBLIC_IP and got.body == b"<p>ok</p>"


def test_pinned_backend_refuses_a_private_ip_and_a_socket_that_reached_one():
    with pytest.raises(UrlRefused):
        PinnedBackend("127.0.0.1")

    class Inner:
        closed = False

        async def connect_tcp(self, host, port, **kw):
            outer = self

            class S:
                async def aclose(self):
                    outer.closed = True

                def get_extra_info(self, _):
                    return ("127.0.0.1", port)  # the socket ended up on loopback although the check said public

            return S()

    inner = Inner()
    pinned = PinnedBackend(PUBLIC_IP, inner=inner)  # type: ignore[arg-type]
    with pytest.raises(UrlRefused, match="reached a forbidden address"):
        asyncio.run(pinned.connect_tcp("ok.example", 443))
    assert inner.closed


def test_pinned_backend_ignores_the_host_it_is_asked_for():
    class Inner:
        seen: list[str] = []

        async def connect_tcp(self, host, port, **kw):
            self.seen.append(host)

            class S:
                async def aclose(self):
                    pass

                def get_extra_info(self, _):
                    return (host, port)

            return S()

    inner = Inner()
    pinned = PinnedBackend(PUBLIC_IP, inner=inner)  # type: ignore[arg-type]
    asyncio.run(pinned.connect_tcp("evil.example", 443))
    assert inner.seen == [PUBLIC_IP]
