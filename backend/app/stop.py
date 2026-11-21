# backend/app/stop.py
"""STOP everything: the browser STOP button cancels tools, agent turns, approvals and the voice session.

The websocket stays open. `busy` tells the browser whether anything is running (voice session,
long tool, text-chat turn, open approval) so the STOP button can show it.
"""

import asyncio
import logging

from app.agent.loop import Emit
from app.agent_wiring import AgentSession
from app.voice import VoiceBridge

log = logging.getLogger("friday.stop")

POLL_S = 0.3


class StopController:
    def __init__(self, emit: Emit, agent: AgentSession, voice: VoiceBridge):
        self._emit = emit
        self._agent = agent
        self._voice = voice
        self._count = 0
        self._monitor: asyncio.Task | None = None

    def running(self) -> int:
        """Number of running things: voice session, long tools, text-chat turns, open approvals."""
        return int(self._voice.active) + self._voice.running_tools + self._agent.running_chats + self._agent.approvals.pending

    async def stop(self) -> list[str]:
        """Cancel everything; safe and quiet-but-confirmed when nothing runs. Returns the cancelled names."""
        cancelled: list[str] = []
        await self._agent.approvals.deny_all()
        cancelled += await self._voice.stop_tools()
        cancelled += await self._agent.cancel_chats()
        if self._voice.active:
            await self._voice.stop()
            cancelled.append("voice")
        await self._emit({"t": "state", "state": "idle"})
        await self._emit({"t": "stopped", "cancelled": cancelled})
        await self._emit({"t": "notice", "text": "Zastaveno"})
        await self.update_busy()
        return cancelled

    async def update_busy(self) -> None:
        count = self.running()
        if count != self._count:
            self._count = count
            await self._emit({"t": "busy", "busy": count > 0, "count": count})

    def start_monitor(self) -> None:
        self._monitor = asyncio.create_task(self._poll())

    async def close(self) -> None:
        monitor, self._monitor = self._monitor, None
        if monitor:
            monitor.cancel()
            await asyncio.gather(monitor, return_exceptions=True)

    async def _poll(self) -> None:
        try:
            while True:
                await asyncio.sleep(POLL_S)
                await self.update_busy()
        except asyncio.CancelledError:
            raise
        except Exception as e:  # the browser is gone; the connection teardown stops us
            log.debug("busy monitor ended: %s", e)
