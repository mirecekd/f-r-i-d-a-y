# backend/app/model3d/tools.py
"""Registration of the generic model_* tools for one browser connection."""

from typing import Any

from app.model3d.session import ModelSession
from app.model3d.tools_edit import register_edit_tools
from app.model3d.tools_query import register_query_tools
from app.voice.tools import ToolRegistry


def register_model_tools(registry: ToolRegistry, ctx: Any) -> ModelSession:
    """Bind model tools to `ctx` (needs .scene and .emit). The registry is per connection."""
    session = ModelSession(ctx)
    register_edit_tools(registry, session)
    register_query_tools(registry, session)
    return session
