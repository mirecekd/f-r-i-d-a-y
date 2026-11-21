# backend/app/tools_friday/__init__.py
"""Model tools for the Live session: scene editing and view panels.

`register_all(registry, ctx)` binds the tools to one browser connection through closures,
so the registry must be built per connection (see main.ws_endpoint).
"""

from app.tools_friday.ctx import Ctx
from app.tools_friday.hermes import register_hermes_tool
from app.tools_friday.scene import register_scene_tools
from app.tools_friday.views import register_view_tools
from app.voice.tools import ToolRegistry

__all__ = ["Ctx", "register_all"]


def register_all(registry: ToolRegistry, ctx: Ctx) -> None:
    register_scene_tools(registry, ctx)
    register_view_tools(registry, ctx)
    register_hermes_tool(registry)  # only when HERMES_URL and HERMES_KEY are set
