# backend/app/mcp/__init__.py
"""MCP client: external tool servers exposed to Friday as approval-gated tools."""

from app.mcp.api import router as api_router
from app.mcp.hub import hub


def register_mcp_tools(registry) -> None:
    hub.register_into(registry)


__all__ = ["api_router", "hub", "register_mcp_tools"]
