# backend/app/webpages/fetch.py
"""Safe page fetcher: the server fetches a URL for the user, so every hop is checked (scheme, port, credentials, deny/allow
lists, public IP only), the connection is pinned to the checked IP, redirects are re-checked, and the body is capped."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin

import httpcore

from app.webpages import config
from app.webpages.pinned import PinnedBackend, tls_context
from app.webpages.urlguard import Resolver, Target, UrlRefused, parse_target, public_ips, system_resolver

MAX_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 5
CONNECT_S, TOTAL_S = 10.0, 20.0
TEXT_TYPES = ("text/html", "application/xhtml+xml", "text/plain")
PDF_TYPE = "application/pdf"
IMAGE_TYPES = ("image/jpeg", "image/png", "image/gif", "image/webp")
ALLOWED_TYPES = (*TEXT_TYPES, PDF_TYPE, *IMAGE_TYPES)
BackendFactory = Callable[[str], httpcore.AsyncNetworkBackend]


@dataclass
class Fetched:
    url: str  # final URL after redirects
    content_type: str  # media type without parameters, lower case
    charset: str | None
    body: bytes
    redirects: int
    ip: str


def _default_backend(ip: str) -> httpcore.AsyncNetworkBackend:
    return PinnedBackend(ip)


def _media_type(headers: dict[str, str]) -> tuple[str, str | None]:
    raw = headers.get("content-type", "")
    media, _, params = raw.partition(";")
    charset = next(
        (p.split("=", 1)[1].strip(" \"'") for p in params.split(";") if p.strip().lower().startswith("charset=")), None
    )
    return media.strip().lower(), charset


async def _hop(target: Target, ip: str, factory: BackendFactory) -> tuple[int, dict[str, str], bytes, str]:
    """One GET to the pinned `ip`; returns (status, headers, body, ip the socket reached). Aborts a body over MAX_BYTES."""
    backend = factory(ip)
    url = httpcore.URL(
        scheme=target.scheme.encode(), host=target.host.encode(), port=target.port, target=target.path.encode()
    )
    headers = [
        (b"Host", target.netloc().encode()),
        (b"User-Agent", config.user_agent().encode()),
        (b"Accept", b"text/html,application/xhtml+xml,text/plain,application/pdf,image/*;q=0.8"),
        (b"Accept-Encoding", b"identity"),
    ]  # no cookies, no auth, no compression
    ext = {"timeout": {"connect": CONNECT_S, "read": TOTAL_S, "write": CONNECT_S, "pool": CONNECT_S}}
    async with httpcore.AsyncConnectionPool(
        ssl_context=tls_context() if target.scheme == "https" else None,
        max_connections=1,
        network_backend=backend,
        retries=0,
    ) as pool:
        async with pool.stream("GET", url, headers=headers, extensions=ext) as resp:
            head = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in resp.headers}
            reached = getattr(backend, "connected_to", None) or ip
            if resp.status // 100 == 3:
                return resp.status, head, b"", reached
            if resp.status >= 400:
                raise UrlRefused(f"the server answered HTTP {resp.status}")
            if head.get("content-encoding", "identity").lower() not in ("identity", ""):
                raise UrlRefused("compressed responses are not accepted")
            media, _ = _media_type(head)
            if media not in ALLOWED_TYPES:
                raise UrlRefused(
                    f"content type {media or 'unknown'!r} is not supported (html, text, pdf and common images only)"
                )
            if head.get("content-length", "").isdigit() and int(head["content-length"]) > MAX_BYTES:
                raise UrlRefused(f"the page is larger than {MAX_BYTES // (1024 * 1024)} MB")
            chunks: list[bytes] = []
            size = 0
            async for chunk in resp.aiter_stream():
                size += len(chunk)
                if size > MAX_BYTES:
                    raise UrlRefused(f"the page is larger than {MAX_BYTES // (1024 * 1024)} MB")
                chunks.append(chunk)
            return resp.status, head, b"".join(chunks), reached


async def fetch(
    url: str, *, resolver: Resolver = system_resolver, backend: BackendFactory = _default_backend
) -> Fetched:
    """Fetch one page or file. Raises UrlRefused with a message fit for the user for anything not allowed or failing."""
    if not config.enabled():
        raise UrlRefused("web fetching is switched off (FRIDAY_WEB_FETCH=0)")
    try:
        async with asyncio.timeout(TOTAL_S):
            return await _follow(url, resolver, backend)
    except TimeoutError as e:
        raise UrlRefused(f"the page did not answer within {int(TOTAL_S)} s") from e
    except (httpcore.TimeoutException, httpcore.NetworkError, httpcore.ProtocolError, OSError) as e:
        raise UrlRefused(f"cannot fetch the page: {type(e).__name__}") from e


async def _follow(url: str, resolver: Resolver, factory: BackendFactory) -> Fetched:
    ports, current = config.allowed_ports(), url
    for hop in range(MAX_REDIRECTS + 1):
        target = parse_target(current, ports)
        if refused := config.host_refusal(target.host):
            raise UrlRefused(refused)
        ips = await public_ips(target.host, target.port, resolver)  # resolved ONCE; the connection goes to this address
        status, head, body, reached = await _hop(target, ips[0], factory)
        if status // 100 != 3:
            media, charset = _media_type(head)
            return Fetched(target.url(), media, charset, body, hop, reached)
        location = head.get("location", "")
        if not location:
            raise UrlRefused(f"HTTP {status} redirect without a Location")
        current = urljoin(target.url(), location)
    raise UrlRefused(f"more than {MAX_REDIRECTS} redirects")
