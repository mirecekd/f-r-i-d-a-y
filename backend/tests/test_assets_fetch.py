# backend/tests/test_assets_fetch.py
"""Asset download guard with a fake transport: allowed host only, size cap, glTF magic, private addresses, idempotence."""

import asyncio

import pytest
from web_helpers import PUBLIC_IP, FakeNet, http_answer, redirect, resolver

from app.assets import fetch, index

ASSET = next(a for a in index.load_index().values() if a.id.startswith("qhome-chair"))
HOST = "raw.githubusercontent.com"
GLB = b"glTF" + b"\x02\x00\x00\x00" + b"x" * 64
BIN = "application/octet-stream"


def run(net: FakeNet, table=None):
    return asyncio.run(fetch.ensure(ASSET, resolver=resolver(table or {HOST: [PUBLIC_IP]}), backend=net.factory))


def test_downloads_once_and_is_idempotent():
    net = FakeNet([http_answer(200, BIN, GLB)])
    assert run(net) is True
    assert index.file_of(ASSET.id).read_bytes() == GLB
    assert run(net) is False  # cached: no second connection
    assert net.connects == [PUBLIC_IP]
    assert not list(index.assets_dir().glob(".*.part"))


def test_wrong_magic_is_refused_and_nothing_is_written():
    with pytest.raises(fetch.UrlRefused, match="glTF"):
        run(FakeNet([http_answer(200, BIN, b"<html>not a model</html>")]))
    assert not index.file_of(ASSET.id).exists()


def test_html_content_type_is_refused():
    with pytest.raises(fetch.UrlRefused, match="binary"):
        run(FakeNet([http_answer(200, "text/html", GLB)]))


def test_declared_and_streamed_size_over_cap_is_refused(monkeypatch):
    monkeypatch.setattr(fetch, "MAX_BYTES", 32)
    with pytest.raises(fetch.UrlRefused, match="25 MB"):
        run(FakeNet([http_answer(200, BIN, GLB)]))
    with pytest.raises(fetch.UrlRefused, match="25 MB"):
        run(FakeNet([http_answer(200, BIN, GLB, length=False)]))
    assert not index.file_of(ASSET.id).exists()


def test_http_error_is_refused():
    with pytest.raises(fetch.UrlRefused, match="404"):
        run(FakeNet([http_answer(404, BIN, b"")]))


def test_host_resolving_to_private_ip_is_refused_without_connecting():
    net = FakeNet([http_answer(200, BIN, GLB)])
    with pytest.raises(fetch.UrlRefused):
        run(net, {HOST: ["10.0.0.5"]})
    assert net.connects == []


@pytest.mark.parametrize("target", [
    "https://127.0.0.1/model.glb", "https://169.254.169.254/latest", "https://evil.example/model.glb",
    "http://raw.githubusercontent.com/x.glb", "https://[::1]/x.glb",
])
def test_redirect_to_private_or_foreign_host_is_refused(target):
    net = FakeNet([redirect(target), http_answer(200, BIN, GLB)])
    with pytest.raises(fetch.UrlRefused):
        run(net, {HOST: [PUBLIC_IP], "evil.example": [PUBLIC_IP]})
    assert net.connects == [PUBLIC_IP]  # only the first, allowed hop was ever connected
    assert not index.file_of(ASSET.id).exists()


def test_redirect_inside_the_allowed_host_is_followed():
    net = FakeNet([redirect(f"https://{HOST}/other.glb"), http_answer(200, BIN, GLB)])
    assert run(net) is True


def test_redirect_loop_is_cut():
    net = FakeNet([redirect(f"https://{HOST}/a.glb")] * 6)
    with pytest.raises(fetch.UrlRefused, match="redirects"):
        run(net)
