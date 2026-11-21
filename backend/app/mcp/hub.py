# backend/app/mcp/hub.py
"""Process-wide MCP state: servers connect lazily once, every browser connection registers the same tools."""

import asyncio
import logging
from typing import Any

from app.mcp.client import Connector, McpServerClient, network_session
from app.mcp.config import ServerSpec, load_specs
from app.mcp.router import build_tool, exposed_name, is_allowed
from app.voice.tools import Tool, ToolRegistry

log = logging.getLogger("friday.mcp")


class McpPool:
    def __init__(self, specs: list[ServerSpec] | None = None, connector: Connector = network_session):
        self._specs = specs
        self._connector = connector
        self._clients: dict[str, McpServerClient] | None = None
        self._discovery: asyncio.Task | None = None

    @property
    def clients(self) -> dict[str, McpServerClient]:
        if self._clients is None:
            specs = self._specs if self._specs is not None else load_specs()
            self._clients = {s.name: McpServerClient(s, self._connector) for s in specs}
        return self._clients

    def discover(self) -> asyncio.Task:
        """Start (once) connecting to every enabled server; the task finishes when all have answered or failed."""
        if self._discovery is None:
            enabled = [c for c in self.clients.values() if c.spec.enabled]
            self._discovery = asyncio.create_task(self._discover(enabled))
        return self._discovery

    @staticmethod
    async def _discover(clients: list[McpServerClient]) -> None:
        await asyncio.gather(*(c.ensure() for c in clients), return_exceptions=True)

    def tools(self) -> list[Tool]:
        out: dict[str, Tool] = {}
        for client in self.clients.values():
            for tool in client.tools:
                if is_allowed(client, tool):
                    out.setdefault(exposed_name(client.spec.name, tool.name), build_tool(client, tool))
        return list(out.values())

    def register_into(self, registry: ToolRegistry) -> None:
        """Add the MCP tools to one connection's registry now, or as soon as discovery finishes."""
        if not any(c.spec.enabled for c in self.clients.values()):
            return
        try:
            task = self.discover()
        except RuntimeError:  # no running loop (sync callers): nothing to connect with
            return
        if task.done():
            self._add(registry)
        else:
            task.add_done_callback(lambda _t: self._add(registry))

    def _add(self, registry: ToolRegistry) -> None:
        for tool in self.tools():
            registry.register(tool)

    async def status(self) -> dict[str, Any]:
        if any(c.spec.enabled for c in self.clients.values()):
            await asyncio.wait({self.discover()}, timeout=30)
        servers = []
        for c in self.clients.values():
            exposed = [exposed_name(c.spec.name, t.name) for t in c.tools if is_allowed(c, t)]
            blocked = [t.name for t in c.tools if not is_allowed(c, t)]
            servers.append(
                {
                    "name": c.spec.name,
                    "transport": c.spec.transport,
                    "enabled": c.spec.enabled,
                    "connected": c.connected,
                    "error": c.error or c.spec.disabled_reason,
                    "discovered": len(c.tools),
                    "exposed": exposed,
                    "blocked": blocked,
                }
            )
        return {"servers": servers}

    async def close(self) -> None:
        await asyncio.gather(*(c.close() for c in self.clients.values()), return_exceptions=True)


hub = McpPool()
