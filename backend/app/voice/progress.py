# backend/app/voice/progress.py
"""Spoken progress for long tools: a short line to the Live model so the voice is not silent while a tool runs.

The line goes through the bridge's `send_text` (turn_complete=True): `send_context` adds a turn WITHOUT asking for a
reply, so the model would never say it. A turn with turn_complete=True interrupts a speaking model, therefore
`say` is skipped while the model or the user is speaking. Switch: env FRIDAY_SPOKEN_PROGRESS (default on; 0/false/off/no disables).
"""

import asyncio
import contextlib
import logging
import os
import time
from collections.abc import AsyncIterator, Awaitable, Callable

log = logging.getLogger("friday.voice.progress")

MAX_CHARS = 120
MIN_GAP_S = 6.0
MAX_PER_CALL = 3
SLOW_AFTER_S = 10.0


def enabled() -> bool:
    return os.getenv("FRIDAY_SPOKEN_PROGRESS", "1").strip().lower() not in {"0", "false", "off", "no"}


def label_of(tool_name: str) -> str:
    """`house_from_sources` -> `house from sources`."""
    return tool_name.replace("_", " ").strip()


class ProgressSpeaker:
    def __init__(
        self,
        send: Callable[[str], Awaitable[None]],
        has_session: Callable[[], bool],
        talking: Callable[[], bool],
        clock: Callable[[], float] = time.monotonic,
    ):
        self._send = send  # delivers one line as a turn the model answers (bridge.send_text)
        self._has_session = has_session
        self._talking = talking  # True while the model or the user is speaking
        self._clock = clock
        self._last = -MIN_GAP_S
        self._counts: dict[str, int] = {}

    async def say(self, text: str, call_id: str = "") -> bool:
        """Send one line (cut to 120 chars) unless disabled, no session, someone is speaking, rate limited or over the per-call cap."""
        if not enabled() or not self._has_session() or self._talking():
            return False
        now = self._clock()
        if now - self._last < MIN_GAP_S or self._counts.get(call_id, 0) >= MAX_PER_CALL:
            return False
        self._last = now
        self._counts[call_id] = self._counts.get(call_id, 0) + 1
        try:
            await self._send(text[:MAX_CHARS])
        except Exception as e:
            log.debug("progress line dropped: %s", e)
            return False
        return True

    @contextlib.asynccontextmanager
    async def watch(self, tool_name: str, call_id: str, slow_after: float = SLOW_AFTER_S) -> AsyncIterator[None]:
        """Around a long tool: one line at the start, one more when it takes longer than `slow_after` seconds."""
        label = label_of(tool_name)
        await self.say(f"Working on {label} (this may take a moment)", call_id)
        slow = asyncio.create_task(self._say_later(f"Still working on {label}", call_id, slow_after))
        try:
            yield
        finally:
            slow.cancel()
            self._counts.pop(call_id, None)

    async def _say_later(self, text: str, call_id: str, delay: float) -> None:
        await asyncio.sleep(delay)
        await self.say(text, call_id)
