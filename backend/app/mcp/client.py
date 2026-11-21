# backend/app/mcp/client.py
"""One MCP server connection: owned by a background task, timeouts everywhere, one reconnect on failure.

The connection lives in its own task because the transport's context managers must be entered and exited by
the same task. Callers only use `ensure()`, `call()` and `close()`; every failure becomes a payload, never a crash.
"""

import asyncio
import logging
import os
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager
from typing import Any

import httpx2
from mcp import ClientSession, types
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client

from app.mcp.config import ServerSpec

log = logging.getLogger("friday.mcp")

Connector = Callable[[ServerSpec], AbstractAsyncContextManager[Any]]  # yields an object with list_tools/call_tool


def auth_headers(spec: ServerSpec) -> dict[str, str]:
    headers = {h: os.environ[env] for h, env in spec.headers_env.items() if os.getenv(env)}
    token = os.getenv(spec.token_env) if spec.token_env else None
    if token:
        headers["Authorization"] = token if token.lower().startswith("bearer ") else f"Bearer {token}"
    return headers


@asynccontextmanager
async def network_session(spec: ServerSpec):
    """Open and initialise a real MCP session over streamable HTTP or SSE."""
    assert spec.url is not None
    headers = auth_headers(spec)
    async with httpx2.AsyncClient(headers=headers, timeout=spec.call_timeout, follow_redirects=True) as http:
        transport = (
            streamable_http_client(spec.url, http_client=http)
            if spec.transport == "streamable-http"
            else sse_client(spec.url, headers=headers, timeout=spec.connect_timeout)
        )
        async with AsyncExitStack() as stack:
            streams = await stack.enter_async_context(transport)
            session = await stack.enter_async_context(ClientSession(streams[0], streams[1]))
            await session.initialize()
            yield session


class McpServerClient:
    def __init__(self, spec: ServerSpec, connector: Connector = network_session):
        self.spec = spec
        self._connector = connector
        self.tools: list[types.Tool] = []
        self.error = ""
        self._session: Any = None
        self._task: asyncio.Task | None = None
        self._ready = asyncio.Event()
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self._session is not None

    async def ensure(self) -> bool:
        """Connect if needed (idempotent, shared by all callers); False when the server is unavailable."""
        async with self._lock:
            if self._session is None and self.spec.enabled:
                await self._start()
            return self._session is not None

    async def _start(self) -> None:
        await self._shutdown()
        self._ready, self._stop, self.error = asyncio.Event(), asyncio.Event(), ""
        self._task = asyncio.create_task(self._run(self._ready, self._stop))
        try:
            await asyncio.wait_for(self._ready.wait(), self.spec.connect_timeout + 5)
        except TimeoutError:
            self.error = "connect timeout"
        if self._session is None:
            (log.warning if self.spec.continue_on_error else log.error)(
                "MCP server %s unavailable: %s", self.spec.name, self.error
            )
            await self._shutdown()

    async def _run(self, ready: asyncio.Event, stop: asyncio.Event) -> None:
        try:
            async with asyncio.timeout(self.spec.connect_timeout):
                cm = self._connector(self.spec)
                session = await cm.__aenter__()
                tools: list[types.Tool] = []
                cursor = None
                while True:
                    page = await session.list_tools(cursor=cursor) if cursor else await session.list_tools()
                    tools += page.tools
                    cursor = page.next_cursor
                    if not cursor:
                        break
        except BaseException as e:
            self.error = f"{type(e).__name__}: {str(e)[:120]}"
            ready.set()
            if isinstance(e, asyncio.CancelledError):
                raise
            return
        self.tools, self._session = tools, session
        ready.set()
        try:
            await stop.wait()
        finally:
            self._session = None
            try:
                await cm.__aexit__(None, None, None)
            except BaseException as e:  # a transport torn down mid-request must not leak out of the task
                log.debug("MCP %s close: %s", self.spec.name, type(e).__name__)

    async def call(self, tool: str, args: dict[str, Any]) -> types.CallToolResult | dict[str, str]:
        """Call a tool; one reconnect when the connection looks dead. Failures return {"error": ...}."""
        for attempt in (1, 2):
            if not await self.ensure():
                return {"error": f"MCP server {self.spec.name} is unavailable ({self.error})"}
            try:
                return await asyncio.wait_for(self._session.call_tool(tool, args), self.spec.call_timeout)
            except TimeoutError:
                return {"error": f"{tool} did not answer within {self.spec.call_timeout:.0f} s"}
            except Exception as e:
                log.warning("MCP %s.%s failed (attempt %d): %s", self.spec.name, tool, attempt, type(e).__name__)
                if attempt == 2:
                    return {"error": f"{tool} failed ({type(e).__name__})"}
                async with self._lock:
                    await self._shutdown()
        return {"error": "unreachable"}

    async def _shutdown(self) -> None:
        task, self._task = self._task, None
        self._stop.set()
        self._session = None
        if task is not None:
            try:
                await asyncio.wait_for(task, 5)
            except BaseException as e:
                if isinstance(e, asyncio.CancelledError) and not task.cancelled():
                    raise
                task.cancel()

    async def close(self) -> None:
        async with self._lock:
            await self._shutdown()
