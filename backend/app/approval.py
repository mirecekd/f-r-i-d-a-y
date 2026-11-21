# backend/app/approval.py
"""Per-connection user approval for risky tools.

`ask` emits `confirm_request` to the browser and waits for its `confirm` answer. A timeout, a
disconnect or a cancelled tool counts as deny and emits `confirm_closed`, so the UI drops the prompt.
"""

import asyncio
import logging
import re
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

log = logging.getLogger("friday.approval")

Emit = Callable[[dict[str, Any]], Awaitable[None]]

DEFAULT_TIMEOUT_S = 60
MAX_VALUE_CHARS = 200
MAX_ITEMS = 20
MAX_DEPTH = 3
SECRET_KEY = re.compile(r"key|token|secret|password", re.IGNORECASE)


def mask_args(value: Any, depth: int = 0) -> Any:
    """Copy of tool args that is safe to show: secret-looking keys masked, long values truncated."""
    if isinstance(value, dict):
        if depth >= MAX_DEPTH:
            return "..."
        items = list(value.items())[:MAX_ITEMS]
        return {str(k): "***" if SECRET_KEY.search(str(k)) else mask_args(v, depth + 1) for k, v in items}
    if isinstance(value, list | tuple):
        return "..." if depth >= MAX_DEPTH else [mask_args(v, depth + 1) for v in value[:MAX_ITEMS]]
    if isinstance(value, str):
        return value if len(value) <= MAX_VALUE_CHARS else value[:MAX_VALUE_CHARS] + "..."
    return value if value is None or isinstance(value, bool | int | float) else str(value)[:MAX_VALUE_CHARS]


class Approvals:
    def __init__(self, emit: Emit):
        self._emit = emit
        self._pending: dict[str, tuple[str, asyncio.Future[bool]]] = {}  # id -> (tool, answer)
        self._allowed: set[str] = set()  # tool names allowed for the rest of this connection

    @property
    def pending(self) -> int:
        return len(self._pending)

    async def ask(self, tool: str, summary: str, args: dict[str, Any], timeout: float = DEFAULT_TIMEOUT_S) -> bool:
        if tool in self._allowed:
            return True
        request_id = uuid.uuid4().hex[:8]
        future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = (tool, future)
        reason = "timeout"
        try:
            await self._emit(
                {
                    "t": "confirm_request",
                    "id": request_id,
                    "tool": tool,
                    "summary": summary,
                    "args": mask_args(args),
                    "expires_in": int(timeout),
                }
            )
            allow = await asyncio.wait_for(future, timeout)
            reason = "allowed" if allow else "denied"
            return allow
        except TimeoutError:
            reason = "timeout"
        except asyncio.CancelledError:
            reason = "cancelled"
            raise
        except Exception as e:  # the browser is gone: the request cannot be answered
            log.warning("confirm_request for %s failed: %s", tool, e)
            reason = "disconnect"
            return False
        finally:
            self._pending.pop(request_id, None)
            if reason != "disconnect":
                await self._close_prompt(request_id, reason)
        return False

    def resolve(self, msg: dict[str, Any]) -> None:
        """Handle the browser message `{t:'confirm', id, allow, remember?}`; unknown ids are ignored."""
        pending = self._pending.get(str(msg.get("id")))
        if pending is None or pending[1].done():
            return
        tool, future = pending
        allow = msg.get("allow") is True
        if allow and msg.get("remember") == "session":
            self._allowed.add(tool)
        future.set_result(allow)

    def reset_grants(self) -> None:
        """New conversation: forget every `remember: session` allow."""
        self._allowed.clear()

    def close(self) -> None:
        """Connection ended: every open question is denied."""
        self._deny_pending()

    async def deny_all(self) -> int:
        """User STOP: deny every open question and tell the browser to drop its prompts."""
        ids = list(self._pending)
        self._deny_pending()
        for request_id in ids:
            await self._close_prompt(request_id, "stopped")
        return len(ids)

    def _deny_pending(self) -> None:
        for _tool, future in self._pending.values():
            if not future.done():
                future.set_result(False)

    async def _close_prompt(self, request_id: str, reason: str) -> None:
        if reason in ("allowed", "denied"):
            return  # the browser answered itself and already closed its prompt
        try:
            await self._emit({"t": "confirm_closed", "id": request_id, "reason": reason})
        except Exception as e:
            log.debug("confirm_closed not delivered: %s", e)
