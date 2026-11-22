# backend/app/agent_wiring.py
"""Glue between main.py and the agent package: per-connection registry, model pinning, text chat."""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Any

from app.agent import live_text
from app.agent.draw import make_draw_tool
from app.agent.loop import Emit, run_agent
from app.agent.prompt import chat_prompt
from app.agent_settings import SettingsMixin, pinned_model
from app.approval import Approvals
from app.assets import register_asset_tools
from app.deck.session import DeckSession
from app.deck.tools import register_deck_tools
from app.entities.tools import register_entity_tools
from app.files import register_file_tools
from app.imaging import register_imaging_tools
from app.mcp import register_mcp_tools
from app.memory.tools import register_memory_tools
from app.model3d.tools import register_model_tools
from app.scene import SceneStore
from app.tools_friday import Ctx, register_all
from app.tools_friday.search import register_search_tool
from app.undo import UndoService
from app.vision import register_vision_tools
from app.voice.language import current_language
from app.voice.tools import Tool, ToolRegistry
from app.webpages.tools import register_web_tools
from app.workshop.tools import register_workshop_tools

log = logging.getLogger("friday.agent")

MAX_HISTORY = 40
Delta = Callable[[str], Awaitable[None]]


class AgentSession(SettingsMixin):
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
        self.models = register_model_tools(self.registry, ctx)
        self.vision = register_vision_tools(self.registry, ctx, lambda: pinned_model("agent"))
        self.files = register_file_tools(self.registry, ctx, self.vision, lambda: pinned_model("agent"))
        register_entity_tools(self.registry, ctx, self.vision, self.files, self.approvals)
        register_imaging_tools(self.registry, ctx, self.models, lambda: pinned_model("agent"))
        self.deck = DeckSession(ctx, self.models, self.files, self.vision)
        register_deck_tools(self.registry, self.deck)
        self.workshop = register_workshop_tools(self.registry, ctx)
        self.assets = register_asset_tools(self.registry, ctx)
        self.web = register_web_tools(self.registry, ctx, self.deck, self.files, self.vision)
        self.undo = UndoService(self.registry, ctx)  # wraps every tool above, adds undo / redo
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
        self.deck.close()
        self.workshop.close()
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
