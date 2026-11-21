# backend/app/webpages/pinned.py
"""Network backend that connects to an already checked IP address instead of resolving the name again (anti DNS rebinding)."""

import ssl
from collections.abc import Iterable
from typing import Any, cast

import httpcore

from app.webpages.urlguard import UrlRefused, ip_refusal


class PinnedBackend(httpcore.AsyncNetworkBackend):
    """`connect_tcp(host, ...)` ignores `host` and connects to `ip`; TLS still verifies the certificate against the real name,
    because httpcore takes the SNI/hostname from the request URL, not from this backend. After connecting, the address the
    socket really reached is checked again."""

    def __init__(self, ip: str, inner: httpcore.AsyncNetworkBackend | None = None) -> None:
        if refused := ip_refusal(ip):
            raise UrlRefused(refused)
        self.ip = ip
        self.inner = inner or cast(httpcore.AsyncNetworkBackend, httpcore.AnyIOBackend())
        self.connected_to: str | None = None

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        stream = await self.inner.connect_tcp(
            self.ip, port, timeout=timeout, local_address=local_address, socket_options=socket_options
        )
        peer = stream.get_extra_info("server_addr")
        peer_ip = str(peer[0]) if isinstance(peer, tuple) and peer else self.ip
        if refused := ip_refusal(peer_ip):
            await stream.aclose()
            raise UrlRefused(f"the connection reached a forbidden address: {refused}")
        self.connected_to = peer_ip
        return stream

    async def connect_unix_socket(
        self, path: str, timeout: float | None = None, socket_options: Iterable[Any] | None = None
    ) -> httpcore.AsyncNetworkStream:
        raise UrlRefused("unix sockets are not allowed")

    async def sleep(self, seconds: float) -> None:
        await self.inner.sleep(seconds)


def tls_context() -> ssl.SSLContext:
    return httpcore.default_ssl_context()
