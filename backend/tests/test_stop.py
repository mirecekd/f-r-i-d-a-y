# backend/tests/test_stop.py
"""STOP: cancels long tools and agent turns, denies approvals, is idempotent, and `busy` follows the count."""

import asyncio
from types import SimpleNamespace

from google.genai import types

from app.approval import Approvals
from app.stop import StopController
from app.voice.tools import Tool, ToolRegistry, ToolRunner


class Sink:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def __call__(self, msg: dict) -> None:
        self.events.append(msg)

    def kinds(self, t: str) -> list[dict]:
        return [e for e in self.events if e["t"] == t]


async def until(cond, timeout: float = 2.0) -> None:
    async def poll() -> None:
        while not cond():
            await asyncio.sleep(0.005)

    await asyncio.wait_for(poll(), timeout)


class FakeVoice:
    """The slice of VoiceBridge that StopController uses, backed by a real ToolRunner."""

    def __init__(self, runner: ToolRunner):
        self.runner = runner
        self.active = False
        self.stopped = 0

    @property
    def running_tools(self) -> int:
        return len(self.runner.long_running)

    async def stop_tools(self) -> list[str]:
        return await self.runner.stop_all()

    async def stop(self) -> None:
        self.active = False
        self.stopped += 1


class FakeAgent:
    def __init__(self, sink: Sink):
        self.approvals = Approvals(sink)
        self.chats: set[asyncio.Task] = set()
        self.turn_cancelled = False

    @property
    def running_chats(self) -> int:
        return len(self.chats)

    async def start_turn(self) -> None:
        async def turn() -> None:
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                self.turn_cancelled = True
                raise

        task = asyncio.create_task(turn())
        self.chats.add(task)
        task.add_done_callback(self.chats.discard)

    async def cancel_chats(self) -> list[str]:
        tasks = list(self.chats)
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        return ["chat"] * len(tasks)


def setup(sink: Sink):
    started = asyncio.Event()
    cancelled: list[bool] = []

    async def slow(_args):
        started.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise
        return {}

    registry = ToolRegistry({"draw": Tool("draw", "d", {"type": "object", "properties": {}}, slow, long=True)})
    agent = FakeAgent(sink)
    runner = ToolRunner(registry, SimpleNamespace(), sink, agent.approvals)
    voice = FakeVoice(runner)
    return StopController(sink, agent, voice), agent, voice, runner, started, cancelled  # type: ignore[arg-type]


def test_stop_cancels_tool_turn_voice_and_denies_approval():
    async def go():
        sink = Sink()
        stopper, agent, voice, runner, started, cancelled = setup(sink)
        await runner.handle([types.FunctionCall(id="c1", name="draw", args={})])
        await started.wait()
        await agent.start_turn()
        voice.active = True
        answer = asyncio.create_task(agent.approvals.ask("risky", "s", {}, timeout=5))
        await until(lambda: sink.kinds("confirm_request"))
        await stopper.update_busy()
        assert sink.kinds("busy")[-1]["busy"] is True

        names = await stopper.stop()

        assert await answer is False
        assert cancelled == [True] and agent.turn_cancelled and voice.stopped == 1
        assert sorted(names) == ["chat", "draw", "voice"]
        assert sink.kinds("stopped")[-1]["cancelled"] == names
        assert sink.kinds("notice")[-1]["text"] == "Zastaveno"
        assert sink.kinds("state")[-1]["state"] == "idle"
        assert sink.kinds("confirm_closed")[-1]["reason"] == "stopped"
        assert {"t": "tool", "id": "c1", "name": "draw", "status": "error"} in sink.events
        assert sink.kinds("busy")[-1]["busy"] is False
        assert stopper.running() == 0

    asyncio.run(go())


def test_stop_is_idempotent_when_idle():
    async def go():
        sink = Sink()
        stopper, *_ = setup(sink)
        assert await stopper.stop() == []
        assert await stopper.stop() == []
        assert len(sink.kinds("stopped")) == 2
        assert not sink.kinds("busy")  # nothing ever ran

    asyncio.run(go())


def test_busy_event_only_when_count_changes():
    async def go():
        sink = Sink()
        stopper, agent, *_ = setup(sink)
        await stopper.update_busy()
        assert not sink.kinds("busy")
        await agent.start_turn()
        await stopper.update_busy()
        await stopper.update_busy()
        assert [e["busy"] for e in sink.kinds("busy")] == [True]
        await stopper.stop()
        assert [e["busy"] for e in sink.kinds("busy")] == [True, False]

    asyncio.run(go())
