# backend/tests/test_imaging_wiring.py
"""The imaging tools are registered on a session with the documented flags and warnings in their descriptions."""

from app import agent_wiring
from app.scene import SceneStore


def test_session_registers_imaging_tools():
    async def emit(msg):
        return None

    from app.voice.tools import ToolRegistry

    tools = agent_wiring.AgentSession(SceneStore(), emit, ToolRegistry()).registry.tools
    for name in ("image_edit", "house_from_sources", "house_refine"):
        assert tools[name].long and tools[name].scheduling == "WHEN_IDLE"
    assert not tools["image_compare"].long
    for name in ("image_edit", "image_compare"):
        assert "originals are always kept" in tools[name].description.lower()
    assert "AI-generated" in tools["image_edit"].description and "faces" in tools["image_edit"].description
