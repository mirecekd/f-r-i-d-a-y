# backend/app/voice/relay.py
"""Downlink half of the voice bridge: Live server content -> browser frames, plus the orb state."""

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from google.genai import types

from app.voice.selfecho import EchoGuard

log = logging.getLogger("friday.voice")

DROP_MAX_S = 8.0  # a dropped echo turn ends at turn_complete or interrupted, at the latest after this long

SendJson = Callable[[dict[str, Any]], Awaitable[None]]
SendBytes = Callable[[bytes], Awaitable[None]]


class Relay:
    def __init__(self, send_json: SendJson, send_bytes: SendBytes, busy: Callable[[], bool]):
        self.send_json = send_json
        self._send_bytes = send_bytes
        self._busy = busy  # True while a long tool runs, so the orb stays in "drawing"
        self._state = ""
        self._text = {"user": "", "assistant": ""}
        self._guard = EchoGuard()
        self._drop_until = 0.0  # monotonic deadline: the model turn answering Friday's own echo is discarded

    async def on_content(self, resp: types.LiveServerMessage) -> None:
        sc = resp.server_content
        if self._dropping() and resp.data:
            return
        if resp.data:
            await self._finish_transcript("user")
            await self.set_state("speaking")
            await self._send_bytes(resp.data)
        if sc is None:
            return
        if sc.input_transcription and sc.input_transcription.text:
            chunk = sc.input_transcription.text
            if not self._dropping() and self._guard.is_echo(self._text["user"] + chunk, time.monotonic()):
                await self._drop_echo_turn()
            if not self._dropping():
                await self._add_transcript("user", chunk)
                await self.set_state("listening")
        if sc.output_transcription and sc.output_transcription.text and not self._dropping():
            await self._finish_transcript("user")
            await self._add_transcript("assistant", sc.output_transcription.text)
            self._guard.remember(self._text["assistant"], time.monotonic())
        if sc.interrupted:
            await self.send_json({"t": "interrupted"})
            await self.end_turn()
        elif sc.turn_complete:
            await self.end_turn()

    async def send_usage(self, usage: types.UsageMetadata) -> None:
        counts = {
            "prompt": usage.prompt_token_count,
            "response": usage.response_token_count,
            "thoughts": usage.thoughts_token_count,
            "total": usage.total_token_count,
        }
        await self.send_json({"t": "usage", **{k: v for k, v in counts.items() if v is not None}})

    def reset(self) -> None:
        """Drop half-built transcripts and the remembered state (new conversation)."""
        self._text = {"user": "", "assistant": ""}
        self._state = ""

    async def _drop_echo_turn(self) -> None:
        """The model heard its own voice: drop the heard text and the answer to it, tell the browser once."""
        log.info("self-echo detected, dropping the turn")
        self._drop_until = time.monotonic() + DROP_MAX_S
        self._text["user"] = ""
        await self.send_json({"t": "interrupted"})
        if not self._guard.notified:
            self._guard.notified = True
            await self.send_json({"t": "notice", "text": "Ozvena potlacena"})

    def _dropping(self) -> bool:
        return time.monotonic() < self._drop_until

    async def end_turn(self) -> None:
        if self._dropping():
            self._drop_until = 0.0
            self._text = {"user": "", "assistant": ""}
            await self.set_state("drawing" if self._busy() else "listening")
            return
        await self._finish_transcript("user")
        await self._finish_transcript("assistant")
        await self.set_state("drawing" if self._busy() else "listening")

    async def set_state(self, state: str) -> None:
        if state != self._state:
            self._state = state
            await self.send_json({"t": "state", "state": state})

    async def _add_transcript(self, role: str, chunk: str) -> None:
        self._text[role] += chunk
        await self.send_json({"t": "transcript", "role": role, "text": self._text[role], "final": False})

    async def _finish_transcript(self, role: str) -> None:
        if self._text[role].strip():
            await self.send_json({"t": "transcript", "role": role, "text": self._text[role].strip(), "final": True})
        self._text[role] = ""
