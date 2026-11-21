# backend/app/agent_wiring.py
"""Glue between main.py and the agent package: per-connection registry, model pinning, text chat."""

import asyncio
import logging
import os
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Any

from app.agent import live_text, prefs
from app.agent.catalog import catalog
from app.agent.draw import make_draw_tool
from app.agent.loop import Emit, run_agent
from app.agent.prompt import chat_prompt
from app.agent.voice_settings import NEXT_SESSION_NOTICE, apply_language, apply_voice, models_fields
from app.approval import Approvals
from app.mcp import register_mcp_tools
from app.memory.tools import register_memory_tools
from app.model3d.tools import register_model_tools
from app.scene import SceneStore
from app.tools_friday import Ctx, register_all
from app.tools_friday.search import register_search_tool
from app.vision import register_vision_tools
from app.voice.language import current_language
from app.voice.session import live_model
from app.voice.tools import Tool, ToolRegistry

log = logging.getLogger("friday.agent")

DEFAULT_MODEL = "gemini-flash-latest"
MAX_HISTORY = 40
Delta = Callable[[str], Awaitable[None]]


def pinned_model(role: str) -> str:
    if role == "chat":
        return live_model()
    return prefs.load()[prefs.ROLES[role]] or os.getenv(f"FRIDAY_{role.upper()}_MODEL") or DEFAULT_MODEL


class AgentSession:
    """One browser connection: its tool registry (incl. `draw`), model pinning and text-chat history."""

    def __init__(self, scene: SceneStore, emit: Emit, base: ToolRegistry):
        self.emit = emit
        self.approvals = Approvals(emit)
        self.registry = ToolRegistry(dict(base.tools))
        ctx = Ctx(scene, emit)
        register_all(self.registry, ctx)
        register_search_tool(self.registry)
        register_mcp_tools(self.registry)  # shared hub, allowlisted + approval-gated tools
        register_memory_tools(self.registry, ctx)
        register_model_tools(self.registry, ctx)
        self.vision = register_vision_tools(self.registry, ctx, lambda: pinned_model("agent"))
        self.registry.register(
            make_draw_tool(lambda: pinned_model("agent"), self.worker_tools, emit)
        )
        self.history: list[dict[str, Any]] = [{"role": "system", "content": chat_prompt(current_language())}]
        self._chats: set[asyncio.Task] = set()
        self._lock = asyncio.Lock()

    def worker_tools(self) -> dict:
        """Tools the agent and text chat call directly: everything except `draw` itself."""
        return {n: self._gated(t) for n, t in self.registry.tools.items() if n != "draw"}

    def _gated(self, tool: Tool) -> Tool:
        """Risky tools called outside the Live session (text chat, agent) ask the user first too."""
        if not tool.risky:
            return tool

        async def handler(args: dict[str, Any]) -> dict[str, Any]:
            summary = tool.confirm_summary(args) if tool.confirm_summary else f"Run {tool.name}"
            if not await self.approvals.ask(tool.name, summary, args):
                return {"error": "denied by user"}
            return await tool.handler(args)

        return replace(tool, handler=handler)

    async def send_models(self) -> None:
        await self.emit(
            {
                "t": "models",
                "catalog": await catalog.get(),
                "pinned": {"agent_model": pinned_model("agent"), "chat_model": pinned_model("chat")},
                **models_fields(pinned_model("chat")),
            }
        )

    async def set_language(self, msg: dict, voice_active: bool = False) -> None:
        error = apply_language(msg)
        if error:
            return await self.emit({"t": "error", "message": error})
        self.history[0] = {"role": "system", "content": chat_prompt(current_language())}
        await self._changed(voice_active)

    async def set_voice(self, msg: dict, voice_active: bool = False) -> None:
        error = apply_voice(pinned_model("chat"), msg)
        if error:
            return await self.emit({"t": "error", "message": error})
        await self._changed(voice_active)

    async def _changed(self, voice_active: bool) -> None:
        await self.send_models()
        if voice_active:
            await self.emit({"t": "notice", "text": NEXT_SESSION_NOTICE})

    async def set_model(self, msg: dict, voice_active: bool = False) -> None:
        role, model = msg.get("role"), str(msg.get("model", ""))
        await catalog.get()
        if role not in prefs.ROLES:
            await self.emit({"t": "error", "message": f"set_model: unknown role {role}"})
        elif catalog.provider_of(model) is None:
            await self.emit({"t": "error", "message": f"set_model: unknown model {model}"})
        elif not catalog.has_role(model, role):
            await self.emit({"t": "error", "message": f"set_model: model {model} is not available for role {role}"})
        else:
            prefs.save_model(role, model)
            await self._changed(voice_active and role == "chat")

    def chat(self, text: str) -> None:
        """Start a text-chat turn in the background so the receive loop keeps running."""
        task = asyncio.create_task(self._chat(text))
        self._chats.add(task)
        task.add_done_callback(self._chats.discard)

    @property
    def running_chats(self) -> int:
        return len(self._chats)

    async def cancel_chats(self) -> list[str]:
        """User STOP: cancel the text-chat turns in flight; returns one `chat` name per cancelled turn."""
        tasks = [t for t in self._chats if not t.done()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        return ["chat"] * len(tasks)

    async def close(self) -> None:
        self.approvals.close()
        for task in list(self._chats):
            task.cancel()
        await asyncio.gather(*self._chats, return_exceptions=True)
        await self.vision.close()

    async def _chat(self, text: str) -> None:
        msg_id = uuid.uuid4().hex[:8]

        async def delta(chunk: str) -> None:
            await self.emit({"t": "chat_delta", "id": msg_id, "text": chunk})

        async with self._lock:
            turn_start = len(self.history)
            self.history.append({"role": "user", "content": text})
            await self.emit({"t": "state", "state": "thinking"})
            try:
                await self._answer(delta)
            except asyncio.CancelledError:
                del self.history[turn_start:]  # drop the half-finished turn: no dangling tool calls
                raise
            except Exception as e:
                log.exception("text chat failed")
                await self.emit({"t": "error", "message": f"chat: {type(e).__name__}: {e}"[:300]})
            finally:
                await self.emit({"t": "state", "state": "idle"})
                self._trim()

    async def _answer(self, delta: Delta) -> None:
        """Text turn through the pinned Live model; if that fails before any text, the agent model answers instead."""
        streamed = False

        async def track(chunk: str) -> None:
            nonlocal streamed
            streamed = True
            await delta(chunk)

        try:
            await live_text.run_turn(pinned_model("chat"), self.history, self.worker_tools(), self.emit, track)
        except Exception as e:
            if streamed:
                raise
            log.warning("live text turn failed (%s: %s); falling back to generateContent", type(e).__name__, e)
            await run_agent(pinned_model("agent"), self.history, self.worker_tools(), self.emit, delta)

    def _trim(self) -> None:
        """Keep the system prompt plus the newest turns, cutting only at a user message."""
        while len(self.history) > MAX_HISTORY:
            nxt = next((i for i in range(2, len(self.history)) if self.history[i]["role"] == "user"), None)
            if nxt is None:
                break
            del self.history[1:nxt]
