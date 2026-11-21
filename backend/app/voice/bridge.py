# backend/app/voice/bridge.py
"""Pump between the browser WebSocket and one logical Gemini Live session.

Up:   binary frames (PCM16 16 kHz) -> realtime audio; chat text -> user turn.
Down: audio (PCM16 24 kHz) -> binary frames; transcripts, tool events and state -> JSON.

The Live connection lasts ~10 min. On GoAway or an unexpected close the bridge reconnects with the
latest resumption handle; the browser only sees a state blip and a `notice` event.
"""

import asyncio
import logging
from typing import Any

from google.genai import types

from app.approval import Approvals
from app.memory.briefing import briefing_or_empty
from app.voice import session as live
from app.voice.frames import FrameForwarder
from app.voice.relay import Relay, SendBytes, SendJson
from app.voice.tools import ToolRegistry, ToolRunner

log = logging.getLogger("friday.voice")

MAX_RETRIES = 5
BACKOFF_BASE_S = 0.5
BACKOFF_MAX_S = 8.0


class _GoAway(Exception):
    """The server announced that it will close the connection soon."""


class ConnectError(RuntimeError):
    """The first Live connection of a session failed; `str()` is the readable text shown in the UI."""

    def __init__(self, model: str, cause: Exception):
        super().__init__(f"voice model {model} did not accept the connection: {cause}")


class VoiceBridge:
    def __init__(
        self, send_json: SendJson, send_bytes: SendBytes, registry: ToolRegistry, approvals: Approvals | None = None
    ):
        self._send_json = send_json
        self._registry = registry
        self._session: Any = None
        self._runner = ToolRunner(registry, None, send_json, approvals)
        self._relay = Relay(send_json, send_bytes, lambda: bool(self._runner.long_running))
        self.audio_profile = "headphones"  # set by the browser's `audio_profile`, read when a session starts
        self._profile = self.audio_profile  # profile of the running session
        self._task: asyncio.Task | None = None
        self._ready = asyncio.Event()
        self._handle: str | None = None  # latest resumption handle (valid ~2 h)
        self._retries = 0  # consecutive failed reconnects
        self.frames = FrameForwarder(lambda: self._session)
        self._briefing = ""  # memory briefing in the system prompt, fetched once per start()

    @property
    def active(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def running_tools(self) -> int:
        return len(self._runner.long_running)

    async def stop_tools(self) -> list[str]:
        return await self._runner.stop_all()

    def set_audio_profile(self, profile: object) -> bool:
        """Stores the browser's output device class; it takes effect at the next session start."""
        if profile not in live.AUDIO_PROFILES:
            return False
        self.audio_profile = str(profile)
        return True

    async def start(self) -> None:
        if self.active:
            return
        self._profile = self.audio_profile
        self._ready.clear()
        self._handle = None
        self._task = asyncio.create_task(self._run())
        await self._ready.wait()

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def reset_context(self) -> None:
        """New conversation: forget the resumption handle, transcripts and briefing so the next start() is a fresh Live session."""
        self._handle = None
        self._briefing = ""
        self._relay.reset()
        await self.frames.handle({"t": "frames_stop"})

    async def send_audio(self, pcm: bytes) -> None:
        if self._session is None:
            return  # reconnecting: the gap is a few hundred ms of audio
        try:
            await self._session.send_realtime_input(
                audio=types.Blob(data=pcm, mime_type=f"audio/pcm;rate={live.INPUT_RATE}")
            )
        except Exception as e:
            log.debug("audio dropped: %s", e)

    async def send_text(self, text: str) -> None:
        if self._session is None:
            return
        try:
            await self._session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part(text=text)]), turn_complete=True
            )
        except Exception as e:
            log.warning("text dropped: %s", e)
            return
        await self._relay.set_state("thinking")

    async def send_context(self, text: str) -> None:
        """Add a text turn to the Live conversation without asking for a reply (like the image source tag)."""
        if self._session is None:
            return
        try:
            await self._session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part(text=text)]), turn_complete=False
            )
        except Exception as e:
            log.debug("context dropped: %s", e)

    async def _run(self) -> None:
        self._retries = 0
        connected_once = False
        config_retried = False
        self._briefing = await briefing_or_empty()
        try:
            while True:
                goaway = False
                try:
                    async with live.connect(self._registry, self._handle, self._briefing, self._profile) as session:
                        self._session = session
                        self._runner.attach(session)
                        connected_once = True
                        await self._relay.set_state("listening")
                        self._ready.set()
                        await self._receive_loop()
                except asyncio.CancelledError:
                    raise
                except _GoAway:
                    log.info("GoAway received, resuming")
                    goaway = True
                except Exception as e:
                    if not connected_once:
                        if not config_retried and live.learn_connect_error(live.live_model(), e):
                            config_retried = True
                            continue  # the model rejected the thinking config: retry once with the learned one
                        raise ConnectError(live.live_model(), e) from e
                    log.warning("voice connection lost: %s: %s", type(e).__name__, e)
                finally:
                    self._session = None
                    self._runner.detach()
                if not goaway:
                    self._retries += 1
                if self._retries > MAX_RETRIES:
                    raise RuntimeError(f"voice reconnect failed after {MAX_RETRIES} attempts")
                await self._send_json({"t": "notice", "text": "reconnecting"})
                await self._relay.set_state("thinking")
                if self._retries:
                    await asyncio.sleep(min(BACKOFF_BASE_S * 2 ** (self._retries - 1), BACKOFF_MAX_S))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception("voice session failed")
            text = str(e) if isinstance(e, ConnectError) else f"voice: {type(e).__name__}: {e}"
            await self._send_json({"t": "error", "message": text[:300]})
        finally:
            await self._runner.cancel_all()
            self._ready.set()
            await self._relay.set_state("idle")

    async def _receive_loop(self) -> None:
        """Run until the connection ends (exception). Any received message proves the link works."""
        # session.receive() ends after each turn_complete, so keep re-entering it.
        while True:
            async for resp in self._session.receive():
                self._retries = 0
                await self._on_response(resp)

    async def _on_response(self, resp: types.LiveServerMessage) -> None:
        if resp.go_away:
            raise _GoAway()
        if (update := resp.session_resumption_update) and update.resumable and update.new_handle:
            self._handle = update.new_handle
        if resp.usage_metadata:
            await self._relay.send_usage(resp.usage_metadata)
        if resp.tool_call_cancellation and resp.tool_call_cancellation.ids:
            await self._runner.cancel(list(resp.tool_call_cancellation.ids))
        if resp.tool_call:
            await self._relay.set_state("thinking")
            await self._runner.handle(resp.tool_call.function_calls or [])
            return
        await self._relay.on_content(resp)
