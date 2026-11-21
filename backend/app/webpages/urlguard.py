# backend/app/webpages/urlguard.py
"""URL and address policy of the page fetcher (SSRF guard): what may be fetched and which IP addresses are public."""

import asyncio
import ipaddress
import re
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import quote, urlsplit

MAX_URL = 2048
TRACKING = re.compile(r"^(utm_[a-z]+|fbclid|gclid|mc_eid|igshid)$", re.I)
_HOST = re.compile(r"^[a-z0-9_]([a-z0-9_-]*[a-z0-9_])?(\.[a-z0-9_]([a-z0-9_-]*[a-z0-9_])?)*$")
_NUMERIC_LABEL = re.compile(r"^(0x[0-9a-f]*|[0-9]+)$", re.I)
_LOCAL_SUFFIXES = (".localhost", ".local", ".internal", ".localdomain", ".home.arpa")
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
Resolver = Callable[[str, int], Awaitable[list[str]]]


class UrlRefused(ValueError):
    """The URL or the address behind it may not be fetched; the message is shown to the user."""


@dataclass(frozen=True)
class Target:
    scheme: str
    host: str  # lower case ASCII (punycode) name or the textual IP without brackets
    port: int
    path: str  # percent-encoded path and query, always starting with /

    @property
    def is_default_port(self) -> bool:
        return self.port == (443 if self.scheme == "https" else 80)

    def netloc(self) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        return host if self.is_default_port else f"{host}:{self.port}"

    def url(self) -> str:
        return f"{self.scheme}://{self.netloc()}{self.path}"


def ip_refusal(value: str) -> str | None:
    """Why this IP literal is not a public internet address (loopback, private, link-local, CGNAT, metadata ...), or None."""
    try:
        addr = ipaddress.ip_address(value.split("%")[0])
    except ValueError:
        return f"{value!r} is not an IP address"
    if isinstance(addr, ipaddress.IPv6Address):
        embedded = addr.ipv4_mapped or addr.sixtofour or (addr.teredo[1] if addr.teredo else None)
        if embedded is None and addr in _NAT64:
            embedded = ipaddress.IPv4Address(int(addr) & 0xFFFFFFFF)
        if embedded is not None:
            return ip_refusal(str(embedded))
        if int(addr) >> 32 == 0:  # ::/96 (unspecified, loopback, IPv4-compatible)
            return f"{addr} is not a public address"
    if (
        addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_unspecified
        or addr.is_reserved
        or addr.is_private
        or not addr.is_global
    ):
        return f"{addr} is a private, local or reserved address"
    return None


def _host_of(raw_host: str) -> str:
    host = raw_host.strip("[]").lower().rstrip(".")
    if not host:
        raise UrlRefused("the URL has no host")
    if ":" in host:
        if "%" in host:
            raise UrlRefused("IPv6 zone identifiers are not allowed")
        try:
            return str(ipaddress.ip_address(host))
        except ValueError as e:
            raise UrlRefused("invalid IPv6 address in the URL") from e
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError as e:
        raise UrlRefused("invalid host name") from e
    last = host.rsplit(".", 1)[-1]
    if _NUMERIC_LABEL.match(last):  # 2130706433, 0x7f.1, 0177.0.0.1 are IPv4 spellings, not names
        try:
            return str(ipaddress.IPv4Address(host))
        except ValueError as e:
            raise UrlRefused("numeric host spellings (decimal, octal, hex) are not allowed") from e
    if len(host) > 253 or not _HOST.match(host) or host == "localhost" or host.endswith(_LOCAL_SUFFIXES):
        raise UrlRefused(f"host {host[:60]!r} is not a public internet name")
    return host


def _clean_query(query: str) -> str:
    kept = [p for p in query.split("&") if p and not TRACKING.match(p.split("=", 1)[0])]
    return "&".join(kept)


def parse_target(url: object, ports: frozenset[int], *, keep_tracking: bool = False) -> Target:
    """Validate and normalise one URL (scheme, credentials, port, host spelling); raises UrlRefused. No DNS here."""
    text = url.strip() if isinstance(url, str) else ""
    if not text:
        raise UrlRefused("the URL is empty")
    if len(text) > MAX_URL:
        raise UrlRefused(f"the URL is longer than {MAX_URL} characters")
    if any(ord(c) <= 0x20 or ord(c) == 0x7F or c == "\\" for c in text):
        raise UrlRefused("the URL contains spaces, control characters or backslashes")
    try:
        parts = urlsplit(text)
        port = parts.port
    except ValueError as e:
        raise UrlRefused("the URL is malformed") from e
    if parts.scheme.lower() not in ("http", "https"):
        raise UrlRefused("only http and https URLs can be fetched")
    if "@" in parts.netloc:
        raise UrlRefused("URLs with a user name or password are not allowed")
    scheme = parts.scheme.lower()
    port = port or (443 if scheme == "https" else 80)
    if port not in ports:
        raise UrlRefused(f"port {port} is not allowed (allowed: {sorted(ports)})")
    host = _host_of(parts.hostname or "")
    path = quote(parts.path or "/", safe="/%:@!$&'()*+,;=~-._")
    query = parts.query if keep_tracking else _clean_query(parts.query)
    if query:
        path += "?" + quote(query, safe="/%:@!$&'()*+,;=~-._?")
    return Target(scheme, host, port, path)


async def system_resolver(host: str, port: int) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(str(i[4][0]) for i in infos))


async def public_ips(host: str, port: int, resolver: Resolver = system_resolver) -> list[str]:
    """Resolve once and require EVERY answer to be public; the caller connects to the returned address, never to the name."""
    if refused := (ip_refusal(host) if _is_ip(host) else None):
        raise UrlRefused(refused)
    try:
        ips = [host] if _is_ip(host) else await resolver(host, port)
    except OSError as e:
        raise UrlRefused(f"cannot resolve {host}") from e
    if not ips:
        raise UrlRefused(f"cannot resolve {host}")
    for ip in ips:
        if refused := ip_refusal(ip):
            raise UrlRefused(f"{host} resolves to a forbidden address: {refused}")
    return ips


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False
