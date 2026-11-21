# backend/app/mcp/api.py
"""GET /api/mcp/status: which MCP servers are connected and which tools are exposed or blocked. No secrets."""

from fastapi import APIRouter

from app.mcp.hub import hub

router = APIRouter()


@router.get("/api/mcp/status")
async def mcp_status():
    return await hub.status()
