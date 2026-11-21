# backend/app/agent/loop.py
"""Tool-calling loop: ask the model, run the tools it requests, feed results back, repeat (max 8 rounds)."""

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from app.agent import llm
from app.voice.tools import Tool

log = logging.getLogger("friday.agent.loop")

MAX_ROUNDS = 8
MAX_RESULT_CHARS = 6000
Emit = Callable[[dict[str, Any]], Awaitable[None]]


def openai_tools(tools: dict[str, Tool]) -> list[dict]:
    return [
        {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
        for t in tools.values()
    ]


async def run_tool(tools: dict[str, Tool], call: dict, emit: Emit) -> str:
    """Execute one model-requested call, emitting `tool` start/ok/error events; the result is always a string."""
    tool = tools.get(call["name"])
    await emit({"t": "tool", "id": call["id"], "name": call["name"], "status": "start"})
    started = time.monotonic()
    try:
        if tool is None:
            raise KeyError(f"unknown tool {call['name']}")
        result = json.dumps(await tool.handler(call["args"]), default=str)
        status = "ok"
    except asyncio.CancelledError:
        await emit({"t": "tool", "id": call["id"], "name": call["name"], "status": "error"})
        raise
    except Exception as e:
        log.warning("agent tool %s failed: %s", call["name"], e)
        result, status = json.dumps({"error": f"{type(e).__name__}: {e}"}), "error"
    ms = int((time.monotonic() - started) * 1000)
    await emit({"t": "tool", "id": call["id"], "name": call["name"], "status": status, "ms": ms})
    return result[:MAX_RESULT_CHARS]


async def run_agent(
    model: str,
    messages: list[dict],
    tools: dict[str, Tool],
    emit: Emit,
    on_delta: llm.OnDelta | None = None,
    max_rounds: int = MAX_ROUNDS,
) -> str:
    """Run the loop on `messages` (appended in place with every assistant/tool turn) and return the final text."""
    declared = openai_tools(tools)
    for _ in range(max_rounds):
        result = await llm.chat(model, messages, declared, on_delta)
        messages.append(llm.assistant_message(result))
        if not result["tool_calls"]:
            return result["text"]
        if on_delta and result["text"]:
            await on_delta("\n")  # keep the text of consecutive rounds apart in one streamed message
        for call in result["tool_calls"]:
            call["id"] = call["id"] or uuid.uuid4().hex[:8]
            output = await run_tool(tools, call, emit)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": output})
    return f"Stopped after {max_rounds} tool rounds without a final answer."
