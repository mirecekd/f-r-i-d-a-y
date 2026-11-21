# backend/app/webpages/config.py
"""Environment switches of the web page feature: FRIDAY_WEB_FETCH, FRIDAY_WEB_PORTS, FRIDAY_WEB_ALLOWLIST, FRIDAY_WEB_DENYLIST."""

import os
from fnmatch import fnmatchcase

from app import __version__

DEFAULT_PORTS = (80, 443)
CONFIGURABLE_PORTS = (8080, 8443)


def enabled() -> bool:
    """False when FRIDAY_WEB_FETCH is 0/false/off/no: no URL is fetched at all."""
    return os.getenv("FRIDAY_WEB_FETCH", "1").strip().lower() not in ("0", "false", "off", "no")


def allowed_ports() -> frozenset[int]:
    """80 and 443 always; 8080 and 8443 only when listed in FRIDAY_WEB_PORTS (comma separated)."""
    extra = {int(p) for p in os.getenv("FRIDAY_WEB_PORTS", "").replace(" ", "").split(",") if p.isdigit()}
    return frozenset(DEFAULT_PORTS) | (extra & set(CONFIGURABLE_PORTS))


def user_agent() -> str:
    return f"FridayBot/{os.getenv('FRIDAY_VERSION') or __version__}"


def _patterns(name: str) -> list[str]:
    return [p.strip().lower() for p in os.getenv(name, "").split(",") if p.strip()]


def host_matches(host: str, pattern: str) -> bool:
    """A pattern with `*` is a glob; without it the host itself and all its subdomains match."""
    if "*" in pattern:
        return fnmatchcase(host, pattern)
    return host == pattern or host.endswith("." + pattern)


def host_refusal(host: str) -> str | None:
    """Why the deny/allow lists refuse `host`, or None. The deny list always wins."""
    if any(host_matches(host, p) for p in _patterns("FRIDAY_WEB_DENYLIST")):
        return f"{host} is on the deny list (FRIDAY_WEB_DENYLIST)"
    allow = _patterns("FRIDAY_WEB_ALLOWLIST")
    if allow and not any(host_matches(host, p) for p in allow):
        return f"{host} is not on the allow list (FRIDAY_WEB_ALLOWLIST)"
    return None
