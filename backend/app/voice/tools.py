# backend/app/voice/tools.py
"""Tool registry and runner for the Live session.

Plain tools block the model until the handler returns. Tools with `long=True` are declared
NON_BLOCKING (see docs/gemini-live/nonblocking-tools.md): the model keeps talking,
the handler runs in a task, and its result is injected later with the chosen scheduling (WHEN_IDLE by default).
New tools (MCP, Hermes, artist) are added with `registry.register(Tool(...))`.
"""

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from google.genai import types

from app.approval import Approvals

log = logging.getLogger("friday.voice.tools")

Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
LATE_RESULT_WAIT_S = 120  # how long a finished long tool waits for a reconnecting session
LATE_RESULT_ATTEMPTS = 3
Emit = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema of the arguments object
    handler: Handler
    long: bool = False
    scheduling: str = "WHEN_IDLE"  # INTERRUPT | WHEN_IDLE | SILENT, used for long tools only
    risky: bool = False  # the user must approve every call (see app/approval.py)
    confirm_summary: Callable[[dict[str, Any]], str] | None = None  # one line shown in the approval prompt


@dataclass
class ToolRegistry:
    tools: dict[str, Tool] = field(default_factory=dict)

    def register(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def tool_config(self) -> list[types.Tool] | None:
        if not self.tools:
            return None
        decls = [
            types.FunctionDeclaration(
                name=t.name,
                description=t.description,
                parameters_json_schema=t.parameters,
                behavior=types.Behavior.NON_BLOCKING if t.long else types.Behavior.BLOCKING,
            )
            for t in self.tools.values()
        ]
        return [types.Tool(function_declarations=decls)]


class ToolRunner:
    """Executes tool calls from one Live session and reports them to the browser."""

    def __init__(self, registry: ToolRegistry, session: Any, emit: Emit, approvals: Approvals | None = None):
        self.registry = registry
        self.approvals = approvals
        self.session: Any = None
        self.emit = emit
        self.long_running: set[asyncio.Task] = set()
        self._tasks_by_call: dict[str, asyncio.Task] = {}
        self._names: dict[str, str] = {}
        self._connected = asyncio.Event()
        if session is not None:
            self.attach(session)

    def attach(self, session: Any) -> None:
        """Point the runner at a (re)connected Live session; waiting late results are delivered to it."""
        self.session = session
        self._connected.set()

    def detach(self) -> None:
        """The Live session is gone; running long tools keep going and wait for `attach`."""
        self.session = None
        self._connected.clear()

    async def cancel(self, call_ids: list[str]) -> None:
        """Server-side cancellation (barge-in): stop the matching long tasks and send no response."""
        for call_id in call_ids:
            task = self._tasks_by_call.pop(call_id, None)
            if task is not None and not task.done():
                task.cancel()
                await self.emit({"t": "tool", "id": call_id, "name": self._names.pop(call_id, ""), "status": "error"})

    async def handle(self, calls: list[types.FunctionCall]) -> None:
        blocking: list[types.FunctionResponse] = []
        for call in calls:
            tool = self.registry.tools.get(call.name or "")
            if tool is None:
                blocking.append(self._response(call, {"error": f"unknown tool {call.name}"}))
            elif tool.long:
                task = asyncio.create_task(self._run_long(tool, call))
                self.long_running.add(task)
                task.add_done_callback(self.long_running.discard)
                if call.id:
                    self._tasks_by_call[call.id] = task
                    self._names[call.id] = tool.name
                    task.add_done_callback(lambda _t, cid=call.id: self._forget(cid))
            else:
                response = await self._execute(tool, call)
                blocking.append(self._response(call, response))
        if blocking:
            await self.session.send_tool_response(function_responses=blocking)

    async def cancel_all(self) -> None:
        for task in list(self.long_running):
            task.cancel()
        await asyncio.gather(*self.long_running, return_exceptions=True)

    async def _run_long(self, tool: Tool, call: types.FunctionCall) -> None:
        response = await self._execute(tool, call)
        reply = self._response(call, response, types.FunctionResponseScheduling[tool.scheduling])
        for _ in range(LATE_RESULT_ATTEMPTS):
            try:  # a reconnect may be in progress: wait for the new session instead of dropping the result
                await asyncio.wait_for(self._connected.wait(), LATE_RESULT_WAIT_S)
                await self.session.send_tool_response(function_responses=[reply])
                return
            except TimeoutError:
                break
            except Exception as e:
                log.warning("late result of %s not delivered, retrying: %s", tool.name, e)
                await asyncio.sleep(1)
        log.warning("late result of %s dropped", tool.name)

    def _forget(self, call_id: str) -> None:
        self._tasks_by_call.pop(call_id, None)
        self._names.pop(call_id, None)

    async def _execute(self, tool: Tool, call: types.FunctionCall) -> dict[str, Any]:
        call_id = call.id or uuid.uuid4().hex[:8]
        if tool.risky and not await self._approved(tool, dict(call.args or {})):
            await self.emit({"t": "tool", "id": call_id, "name": tool.name, "status": "error"})
            return {"error": "denied by user"}
        await self.emit({"t": "tool", "id": call_id, "name": tool.name, "status": "start"})
        started = time.monotonic()
        try:
            response = await tool.handler(dict(call.args or {}))
            status = "ok"
        except Exception as e:
            log.exception("tool %s failed", tool.name)
            response = {"error": f"{type(e).__name__}: {e}"}
            status = "error"
        ms = int((time.monotonic() - started) * 1000)
        await self.emit({"t": "tool", "id": call_id, "name": tool.name, "status": status, "ms": ms})
        return response

    async def _approved(self, tool: Tool, args: dict[str, Any]) -> bool:
        if self.approvals is None:
            return False  # a risky tool without anyone to ask never runs
        summary = tool.confirm_summary(args) if tool.confirm_summary else f"Run {tool.name}"
        return await self.approvals.ask(tool.name, summary, args)

    @staticmethod
    def _response(
        call: types.FunctionCall,
        response: dict[str, Any],
        scheduling: types.FunctionResponseScheduling | None = None,
    ) -> types.FunctionResponse:
        return types.FunctionResponse(id=call.id, name=call.name, response=response, scheduling=scheduling)
