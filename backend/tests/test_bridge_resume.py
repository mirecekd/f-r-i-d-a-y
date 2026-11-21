# backend/tests/test_bridge_resume.py
"""VoiceBridge reconnect, resumption, tool cancellation and usage, against a fake Live session."""

import asyncio
from collections.abc import Sequence
from contextlib import asynccontextmanager
from typing import Any

from google.genai import types

from app.voice import Tool, ToolRegistry, VoiceBridge
from app.voice import bridge as bridge_mod
from app.voice import session as live


class FakeSession:
    """Scripted Live session: items in `script` are messages to yield or exceptions to raise."""

    def __init__(self, script: list[Any]):
        self.queue: asyncio.Queue = asyncio.Queue()
        for item in script:
            self.queue.put_nowait(item)
        self.tool_responses: list[Any] = []

    async def receive(self):
        while True:
            item = await self.queue.get()
            if isinstance(item, BaseException):
                raise item
            yield item

    async def send_tool_response(self, function_responses):
        self.tool_responses.extend(function_responses)

    async def send_realtime_input(self, **_):
        pass

    async def send_client_content(self, **_):
        pass


def handle_msg(handle: str, resumable: bool = True) -> types.LiveServerMessage:
    return types.LiveServerMessage(
        session_resumption_update=types.LiveServerSessionResumptionUpdate(new_handle=handle, resumable=resumable)
    )


GO_AWAY = types.LiveServerMessage(go_away=types.LiveServerGoAway(time_left="5s"))


def audio_msg() -> types.LiveServerMessage:
    part = types.Part(inline_data=types.Blob(data=b"\x01\x02", mime_type="audio/pcm"))
    return types.LiveServerMessage(server_content=types.LiveServerContent(model_turn=types.Content(parts=[part])))


class Harness:
    def __init__(self, monkeypatch, sessions: Sequence[FakeSession | Exception], registry: ToolRegistry | None = None):
        self.events: list[dict] = []
        self.audio: list[bytes] = []
        self.handles: list[str | None] = []
        self.sessions = list(sessions)
        monkeypatch.setattr(bridge_mod, "BACKOFF_BASE_S", 0)

        @asynccontextmanager
        async def fake_connect(_registry, handle=None, briefing=""):
            self.handles.append(handle)
            item = self.sessions.pop(0)
            if isinstance(item, Exception):
                raise item
            yield item

        monkeypatch.setattr(live, "connect", fake_connect)

        async def send_json(m):
            self.events.append(m)

        async def send_bytes(b):
            self.audio.append(b)

        self.bridge = VoiceBridge(send_json, send_bytes, registry or ToolRegistry())

    async def until(self, cond, timeout: float = 3.0):
        async def poll():
            while not cond():
                await asyncio.sleep(0.01)

        await asyncio.wait_for(poll(), timeout)

    def kinds(self, t: str) -> list[dict]:
        return [e for e in self.events if e["t"] == t]


def test_goaway_reconnects_with_latest_handle(monkeypatch):
    async def go():
        s1 = FakeSession([handle_msg("h1"), handle_msg("h2"), GO_AWAY])
        s2 = FakeSession([audio_msg()])
        h = Harness(monkeypatch, [s1, s2])
        await h.bridge.start()
        await h.until(lambda: h.audio)
        await h.bridge.stop()
        assert h.handles == [None, "h2"]
        assert {"t": "notice", "text": "reconnecting"} in h.events
        assert {"t": "state", "state": "thinking"} in h.events  # the blip
        assert h.events[-1] == {"t": "state", "state": "idle"}
        assert not h.kinds("error")

    asyncio.run(go())


def test_non_resumable_update_does_not_replace_handle(monkeypatch):
    async def go():
        s1 = FakeSession([handle_msg("h1"), handle_msg("bad", resumable=False), GO_AWAY])
        h = Harness(monkeypatch, [s1, FakeSession([audio_msg()])])
        await h.bridge.start()
        await h.until(lambda: h.audio)
        await h.bridge.stop()
        assert h.handles == [None, "h1"]

    asyncio.run(go())


def test_unexpected_close_retries_then_recovers(monkeypatch):
    async def go():
        s1 = FakeSession([handle_msg("h1"), ConnectionError("1006")])
        h = Harness(monkeypatch, [s1, OSError("down"), OSError("down"), FakeSession([audio_msg()])])
        await h.bridge.start()
        await h.until(lambda: h.audio)
        await h.bridge.stop()
        assert h.handles == [None, "h1", "h1", "h1"]
        assert not h.kinds("error")

    asyncio.run(go())


def test_gives_up_after_five_failed_retries(monkeypatch):
    async def go():
        s1 = FakeSession([handle_msg("h1"), ConnectionError("1006")])
        h = Harness(monkeypatch, [s1] + [OSError("down")] * 5)
        await h.bridge.start()
        await h.until(lambda: h.kinds("error"))
        await h.until(lambda: not h.bridge.active)
        assert len(h.handles) == 6  # first connect + 5 retries
        assert "reconnect failed" in h.kinds("error")[0]["message"]
        assert h.events[-1] == {"t": "state", "state": "idle"}

    asyncio.run(go())


def test_first_connect_failure_is_reported_without_retry(monkeypatch):
    async def go():
        h = Harness(monkeypatch, [RuntimeError("no key")])
        await h.bridge.start()
        await h.until(lambda: h.kinds("error"))
        assert len(h.handles) == 1

    asyncio.run(go())


def test_usage_metadata_is_forwarded(monkeypatch):
    async def go():
        usage = types.UsageMetadata(prompt_token_count=10, response_token_count=4, total_token_count=14)
        h = Harness(monkeypatch, [FakeSession([types.LiveServerMessage(usage_metadata=usage)])])
        await h.bridge.start()
        await h.until(lambda: h.kinds("usage"))
        await h.bridge.stop()
        assert h.kinds("usage") == [{"t": "usage", "prompt": 10, "response": 4, "total": 14}]

    asyncio.run(go())


def draw_registry(started: asyncio.Event, release: asyncio.Event) -> ToolRegistry:
    async def handler(_args):
        started.set()
        await release.wait()
        return {"output": "done"}

    reg = ToolRegistry()
    reg.register(Tool(name="draw", description="d", parameters={"type": "object"}, handler=handler, long=True))
    return reg


def call_msg(call_id: str) -> types.LiveServerMessage:
    call = types.FunctionCall(id=call_id, name="draw", args={})
    return types.LiveServerMessage(tool_call=types.LiveServerToolCall(function_calls=[call]))


def test_long_tool_survives_reconnect_and_delivers_to_new_session(monkeypatch):
    async def go():
        started, release = asyncio.Event(), asyncio.Event()
        s1 = FakeSession([handle_msg("h1"), call_msg("c1"), GO_AWAY])
        s2 = FakeSession([])
        h = Harness(monkeypatch, [s1, s2], draw_registry(started, release))
        await h.bridge.start()
        await asyncio.wait_for(started.wait(), 3)
        await h.until(lambda: h.handles == [None, "h1"])
        release.set()
        await h.until(lambda: s2.tool_responses)
        await h.bridge.stop()
        assert s1.tool_responses == []
        assert s2.tool_responses[0].id == "c1" and s2.tool_responses[0].response == {"output": "done"}

    asyncio.run(go())


def test_tool_call_cancellation_cancels_task_without_response(monkeypatch):
    async def go():
        started, release = asyncio.Event(), asyncio.Event()
        cancel = types.LiveServerMessage(tool_call_cancellation=types.LiveServerToolCallCancellation(ids=["c1"]))
        s1 = FakeSession([call_msg("c1")])
        h = Harness(monkeypatch, [s1], draw_registry(started, release))
        await h.bridge.start()
        await asyncio.wait_for(started.wait(), 3)
        s1.queue.put_nowait(cancel)
        await h.until(lambda: not h.bridge._runner.long_running)
        release.set()
        await asyncio.sleep(0.05)
        await h.bridge.stop()
        assert s1.tool_responses == []
        assert {"t": "tool", "id": "c1", "name": "draw", "status": "error"} in h.events

    asyncio.run(go())
