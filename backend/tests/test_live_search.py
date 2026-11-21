# backend/tests/test_live_search.py
"""The Live config carries Google's built-in search next to our function declarations."""

from google.genai import types

from app.voice.session import build_config
from app.voice.tools import Tool, ToolRegistry


def live_tools(registry: ToolRegistry) -> list[types.Tool]:
    tools = build_config(registry).tools or []
    assert all(isinstance(t, types.Tool) for t in tools)
    return [t for t in tools if isinstance(t, types.Tool)]


async def _noop(args):
    return {}


def test_google_search_added_next_to_function_declarations():
    registry = ToolRegistry()
    registry.register(Tool(name="slow", description="d", parameters={"type": "object"}, handler=_noop, long=True))
    tools = live_tools(registry)
    assert len(tools) == 2
    assert [d.name for d in tools[0].function_declarations or []] == ["slow"]
    assert tools[1].google_search is not None


def test_google_search_present_without_function_tools():
    tools = live_tools(ToolRegistry())
    assert len(tools) == 1 and tools[0].google_search is not None


def test_function_web_search_is_not_declared_to_live():
    registry = ToolRegistry()
    registry.register(Tool(name="web_search", description="d", parameters={"type": "object"}, handler=_noop))
    tools = live_tools(registry)
    assert len(tools) == 1 and tools[0].google_search is not None
