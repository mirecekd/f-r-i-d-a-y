# backend/app/voice/relay.py
"""Downlink half of the voice bridge: Live server content -> browser frames, plus the orb state."""

from collections.abc import Awaitable, Callable
from typing import Any

from google.genai import types

SendJson = Callable[[dict[str, Any]], Awaitable[None]]
SendBytes = Callable[[bytes], Awaitable[None]]


class Relay:
    def __init__(self, send_json: SendJson, send_bytes: SendBytes, busy: Callable[[], bool]):
        self.send_json = send_json
        self._send_bytes = send_bytes
        self._busy = busy  # True while a long tool runs, so the orb stays in "drawing"
        self._state = ""
        self._text = {"user": "", "assistant": ""}

    async def on_content(self, resp: types.LiveServerMessage) -> None:
        sc = resp.server_content
        if resp.data:
            await self._finish_transcript("user")
            await self.set_state("speaking")
            await self._send_bytes(resp.data)
        if sc is None:
            return
        if sc.input_transcription and sc.input_transcription.text:
            await self._add_transcript("user", sc.input_transcription.text)
            await self.set_state("listening")
        if sc.output_transcription and sc.output_transcription.text:
            await self._finish_transcript("user")
            await self._add_transcript("assistant", sc.output_transcription.text)
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

    async def end_turn(self) -> None:
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
