# backend/app/mcp/config.py
"""mcp_servers.json: which MCP servers Friday connects to. Secrets are referenced by env var NAME only.

Lookup: FRIDAY_MCP_CONFIG (empty = none), else $FRIDAY_DATA_DIR/mcp_servers.json (default /srv/data), else the
file shipped next to the app. Format (the common `mcpServers` layout):
  {"mcpServers": {"<name>": {"transport": "streamable-http" | "sse",
     "url" | "url_env" (+ "path"), "token_env", "headers_env": {"Header": "ENV_NAME"},
     "allowed_tools": [raw MCP tool names], "tool_policies": {"<tool>": {"risky": false, "long": true,
     "allowed_names": [...]}}, "continue_on_error": true, "connect_timeout": 15, "call_timeout": 60}}}
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("friday.mcp")

SHIPPED = Path(__file__).resolve().parent.parent.parent / "mcp_servers.json"
TRANSPORTS = ("streamable-http", "sse")


@dataclass(frozen=True)
class ServerSpec:
    name: str
    transport: str = "streamable-http"
    url: str | None = None  # None: the url_env variable is not set, the server is disabled
    disabled_reason: str = ""
    token_env: str = ""
    headers_env: dict[str, str] = field(default_factory=dict)
    allowed_tools: tuple[str, ...] = ()
    policies: dict[str, dict[str, Any]] = field(default_factory=dict)
    continue_on_error: bool = True
    connect_timeout: float = 15.0
    call_timeout: float = 60.0

    @property
    def enabled(self) -> bool:
        return self.url is not None


def config_path() -> Path | None:
    override = os.getenv("FRIDAY_MCP_CONFIG")
    if override is not None:
        return Path(override) if override else None
    for path in (Path(os.getenv("FRIDAY_DATA_DIR", "/srv/data")) / "mcp_servers.json", SHIPPED):
        if path.is_file():
            return path
    return None


def _spec(name: str, raw: dict[str, Any]) -> ServerSpec:
    url, reason = raw.get("url"), ""
    if raw.get("url_env"):
        url = os.getenv(raw["url_env"]) or url
        reason = f"{raw['url_env']} is not set"
    if url and raw.get("path"):
        url = f"{url.rstrip('/')}/{str(raw['path']).lstrip('/')}"
    transport = raw.get("transport", "streamable-http")
    if transport not in TRANSPORTS:
        url, reason = None, f"unsupported transport {transport}"
    allowed = tuple(raw.get("allowed_tools") or ())
    if url and not allowed:
        log.warning("MCP server %s has no allowed_tools: tools are discovered but none is exposed", name)
    return ServerSpec(
        name=name,
        transport=transport,
        url=url or None,
        disabled_reason="" if url else reason or "no url",
        token_env=raw.get("token_env", ""),
        headers_env=dict(raw.get("headers_env") or {}),
        allowed_tools=allowed,
        policies=dict(raw.get("tool_policies") or {}),
        continue_on_error=bool(raw.get("continue_on_error", True)),
        connect_timeout=float(raw.get("connect_timeout", 15)),
        call_timeout=float(raw.get("call_timeout", 60)),
    )


def load_specs(path: Path | None = None) -> list[ServerSpec]:
    path = path or config_path()
    if path is None:
        return []
    try:
        servers = json.loads(path.read_text()).get("mcpServers", {})
        return [_spec(name, raw) for name, raw in servers.items()]
    except Exception as e:
        log.warning("MCP config %s could not be loaded (%s); running without MCP tools", path, type(e).__name__)
        return []
