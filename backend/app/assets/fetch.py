# backend/app/assets/fetch.py
"""Download one indexed model into <FRIDAY_DATA_DIR>/assets/<id>.glb. Reuses the page fetcher's SSRF guard (public IPs only,
connection pinned to the checked address, redirects re-checked) and adds: only hosts present in the index, a 25 MB cap,
a glTF magic check and an atomic, idempotent write."""

import asyncio
import os
from urllib.parse import urljoin

import httpcore

from app.assets import index
from app.assets.index import Asset
from app.webpages import fetch as page_fetch
from app.webpages.pinned import tls_context
from app.webpages.urlguard import Resolver, UrlRefused, parse_target, public_ips, system_resolver

MAX_BYTES = 25 * 1024 * 1024
MAX_REDIRECTS = 3
TOTAL_S = 60.0
MAGIC = b"glTF"
BINARY_TYPES = ("application/octet-stream", "model/gltf-binary", "binary/octet-stream", "application/x-binary")


async def _hop(url: str, resolver: Resolver, factory: page_fetch.BackendFactory) -> tuple[int, dict[str, str], bytes]:
    target = parse_target(url, frozenset({443}), keep_tracking=True)
    if target.scheme != "https" or target.host not in index.allowed_hosts():
        raise UrlRefused(f"{target.host} is not a host of the asset index")
    ip = (await public_ips(target.host, target.port, resolver))[0]
    url_obj = httpcore.URL(scheme=b"https", host=target.host.encode(), port=target.port, target=target.path.encode())
    headers = [(b"Host", target.netloc().encode()), (b"User-Agent", b"FridayAssets/1"), (b"Accept", b"model/gltf-binary,*/*;q=0.5"),
               (b"Accept-Encoding", b"identity")]
    ext = {"timeout": {"connect": 10.0, "read": 30.0, "write": 10.0, "pool": 10.0}}
    async with httpcore.AsyncConnectionPool(ssl_context=tls_context(), max_connections=1, network_backend=factory(ip), retries=0) as pool:
        async with pool.stream("GET", url_obj, headers=headers, extensions=ext) as resp:
            head = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in resp.headers}
            if resp.status // 100 == 3:
                return resp.status, head, b""
            if resp.status != 200:
                raise UrlRefused(f"the model server answered HTTP {resp.status}")
            if head.get("content-encoding", "identity").lower() not in ("identity", ""):
                raise UrlRefused("compressed responses are not accepted")
            if head.get("content-type", "").partition(";")[0].strip().lower() not in BINARY_TYPES:
                raise UrlRefused("the answer is not a binary model file")
            if head.get("content-length", "").isdigit() and int(head["content-length"]) > MAX_BYTES:
                raise UrlRefused("the model is larger than 25 MB")
            chunks: list[bytes] = []
            size = 0
            async for chunk in resp.aiter_stream():
                size += len(chunk)
                if size > MAX_BYTES:
                    raise UrlRefused("the model is larger than 25 MB")
                chunks.append(chunk)
            return resp.status, head, b"".join(chunks)


async def _download(url: str, resolver: Resolver, factory: page_fetch.BackendFactory) -> bytes:
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        status, head, body = await _hop(current, resolver, factory)
        if status // 100 != 3:
            if not body.startswith(MAGIC):
                raise UrlRefused("the file is not a glTF binary (.glb)")
            return body
        if not head.get("location"):
            raise UrlRefused(f"HTTP {status} redirect without a Location")
        current = urljoin(current, head["location"])
    raise UrlRefused(f"more than {MAX_REDIRECTS} redirects")


def _write_atomic(asset_id: str, body: bytes) -> None:
    path = index.file_of(asset_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{asset_id}.{os.getpid()}.part")
    try:
        tmp.write_bytes(body)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


async def ensure(asset: Asset, *, resolver: Resolver = system_resolver, backend: page_fetch.BackendFactory = page_fetch._default_backend) -> bool:
    """Make sure the model is cached; returns True when it was downloaded now, False when it was already there.
    Raises UrlRefused with a message fit for the user."""
    path = index.file_of(asset.id)
    if path.is_file() and path.stat().st_size > 0:
        return False
    try:
        async with asyncio.timeout(TOTAL_S):
            body = await _download(asset.url, resolver, backend)
    except TimeoutError as e:
        raise UrlRefused("the model server did not answer in time") from e
    except (httpcore.TimeoutException, httpcore.NetworkError, httpcore.ProtocolError, OSError) as e:
        raise UrlRefused(f"cannot download the model: {type(e).__name__}") from e
    await asyncio.to_thread(_write_atomic, asset.id, body)
    return True
