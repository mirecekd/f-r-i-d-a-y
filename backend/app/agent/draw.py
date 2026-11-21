# backend/app/agent/draw.py
"""The long `draw(request)` voice tool: runs the executing agent with the pinned agent model."""

from collections.abc import Callable
from typing import Any

from app.agent.loop import Emit, run_agent
from app.agent.prompt import AGENT_PROMPT
from app.voice.tools import Tool

DRAW_DESCRIPTION = (
    "Draw, build or change something in the shared 3D scene or show a visual panel. Takes a while: it hands the "
    "request to the drawing agent and returns a short summary when done. Describe what the user wants in full."
)


def make_draw_tool(model_for: Callable[[], str], scene_tools: Callable[[], dict[str, Tool]], emit: Emit) -> Tool:
    """`model_for` returns the pinned agent model, `scene_tools` the tools the agent may use (never `draw`)."""

    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        request = str(args.get("request", "")).strip()
        if not request:
            return {"error": "request is empty"}
        messages = [{"role": "system", "content": AGENT_PROMPT}, {"role": "user", "content": request}]
        summary = await run_agent(model_for(), messages, scene_tools(), emit)
        return {"ok": True, "summary": summary}

    return Tool(
        name="draw",
        description=DRAW_DESCRIPTION,
        parameters={
            "type": "object",
            "properties": {"request": {"type": "string", "description": "What to draw or show, in full detail."}},
            "required": ["request"],
        },
        handler=handler,
        long=True,
        scheduling="WHEN_IDLE",
    )
