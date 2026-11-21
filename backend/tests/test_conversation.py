# backend/tests/test_conversation.py
"""new_conversation: stops first, clears chat context, keeps scene and settings, re-fetches the briefing."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

from fastapi.testclient import TestClient
from google.genai import types

from app import agent_wiring, main
from app.agent_wiring import AgentSession
from app.conversation import new_conversation
from app.model3d.proposals import Proposal
from app.scene import SceneStore
from app.stop import StopController
from app.voice import Tool, ToolRegistry, VoiceBridge
from app.voice import bridge as bridge_mod
from app.voice import session as live
from app.voice.tools import ToolRunner


class Sink:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def __call__(self, msg: dict) -> None:
        self.events.append(msg)

    def kinds(self, t: str) -> list[dict]:
        return [e for e in self.events if e["t"] == t]


def resumption(handle: str) -> types.LiveServerMessage:
    return types.LiveServerMessage(
        session_resumption_update=types.LiveServerSessionResumptionUpdate(new_handle=handle, resumable=True)
    )


class ScriptedSession:
    """Fake Live session: announces one resumption handle, then stays open."""

    def __init__(self, handle: str):
        self.handle = handle

    async def receive(self):
        yield resumption(self.handle)
        await asyncio.sleep(30)

    async def send_realtime_input(self, **_): ...
    async def send_tool_response(self, *_a, **_k): ...


def build(monkeypatch, sink: Sink, registry: ToolRegistry | None = None):
    """Real AgentSession + VoiceBridge + StopController; the Live connection is a fake."""
    seen: list[tuple[str | None, str]] = []
    briefings = iter(["brief-1", "brief-2", "brief-3"])

    @asynccontextmanager
    async def fake_connect(_reg, handle=None, briefing="", profile="headphones"):
        seen.append((handle, briefing))
        yield ScriptedSession("h-old")

    async def fake_briefing() -> str:
        return next(briefings)

    monkeypatch.setattr(live, "connect", fake_connect)
    monkeypatch.setattr(bridge_mod, "briefing_or_empty", fake_briefing)
    scene = SceneStore()
    agent = AgentSession(scene, sink, registry or ToolRegistry())
    voice = VoiceBridge(sink, sink_bytes, agent.registry, agent.approvals)
    return scene, agent, voice, StopController(sink, agent, voice), seen


async def sink_bytes(_b: bytes) -> None:
    return None


def reset(msg, sink, scene, agent, voice, stopper):
    return new_conversation(msg, sink, scene, agent, voice, stopper)


def test_clears_history_to_system_prompt_and_grants(monkeypatch):
    async def go():
        sink = Sink()
        scene, agent, voice, stopper, _ = build(monkeypatch, sink)
        system = agent.history[0]
        agent.history += [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}]
        agent.approvals._allowed.add("hermes")
        scene.apply([{"op": "add", "obj": {"id": "a", "kind": "box"}}])
        await reset({"t": "new_conversation"}, sink, scene, agent, voice, stopper)
        assert agent.history == [system]
        assert agent.approvals._allowed == set()
        assert [o["id"] for o in scene.objects()] == ["a"]  # scene kept
        assert sink.kinds("conversation_reset") == [{"t": "conversation_reset", "clear_scene": False}]
        assert {"t": "notice", "text": "Nova konverzace"} in sink.events
        assert not any(e["t"] == "scene" for e in sink.events)

    asyncio.run(go())


def test_clear_scene_flag_clears_scene_and_tells_browser(monkeypatch):
    async def go():
        sink = Sink()
        scene, agent, voice, stopper, _ = build(monkeypatch, sink)
        scene.apply([{"op": "add", "obj": {"id": "a", "kind": "box"}}])
        scene.select(["a"])
        await reset({"t": "new_conversation", "clear_scene": True}, sink, scene, agent, voice, stopper)
        assert scene.objects() == [] and scene.selected == []
        assert {"t": "scene", "ops": [{"op": "clear"}]} in sink.events
        assert sink.kinds("conversation_reset")[0]["clear_scene"] is True

    asyncio.run(go())


def test_voice_context_dropped_and_briefing_fetched_again(monkeypatch):
    async def go():
        sink = Sink()
        scene, agent, voice, stopper, seen = build(monkeypatch, sink)
        await voice.start()
        for _ in range(100):
            if voice._handle:
                break
            await asyncio.sleep(0.01)
        assert voice._handle == "h-old"
        await reset({"t": "new_conversation"}, sink, scene, agent, voice, stopper)
        assert not voice.active and voice._handle is None and voice._briefing == ""
        await voice.start()
        await voice.stop()
        assert seen == [(None, "brief-1"), (None, "brief-2")]  # fresh session, fresh briefing, no resumption

    asyncio.run(go())


def test_idempotent_and_safe_when_idle(monkeypatch):
    async def go():
        sink = Sink()
        scene, agent, voice, stopper, _ = build(monkeypatch, sink)
        for _ in range(3):
            await reset({"t": "new_conversation"}, sink, scene, agent, voice, stopper)
        assert len(agent.history) == 1
        assert len(sink.kinds("conversation_reset")) == 3

    asyncio.run(go())


def test_cancels_running_long_tool_and_turn_first(monkeypatch):
    async def go():
        sink = Sink()
        started, cancelled = asyncio.Event(), []

        async def slow(_args):
            started.set()
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                cancelled.append(True)
                raise
            return {}

        registry = ToolRegistry({"slowjob": Tool("slowjob", "d", {"type": "object", "properties": {}}, slow, long=True)})
        scene, agent, voice, stopper, _ = build(monkeypatch, sink, registry)
        runner = ToolRunner(agent.registry, SimpleNamespace(), sink, agent.approvals)
        voice._runner = runner
        await runner.handle([types.FunctionCall(id="c1", name="slowjob", args={})])
        await started.wait()
        await reset({"t": "new_conversation"}, sink, scene, agent, voice, stopper)
        assert cancelled == [True] and runner.long_running == set()
        assert sink.events.index({"t": "stopped", "cancelled": ["slowjob"]}) < sink.events.index(
            {"t": "conversation_reset", "clear_scene": False}
        )

    asyncio.run(go())


def test_proposals_and_model_pointer_cleared(monkeypatch):
    async def go():
        sink = Sink()
        scene, agent, voice, stopper, _ = build(monkeypatch, sink)
        agent.models.current = "m1"
        agent.models.book._open["p1"] = Proposal("p1", "m1", [], "", [], ["g1", "g2"])
        scene.apply([{"op": "add", "obj": {"id": "g1", "kind": "box"}}])
        await reset({"t": "new_conversation"}, sink, scene, agent, voice, stopper)
        assert agent.models.current is None and not agent.models.book._open
        assert {"t": "scene", "ops": [{"op": "del", "id": "g2"}, {"op": "del", "id": "g1"}]} in sink.events

    asyncio.run(go())


def test_over_websocket_resets_history_and_replies():
    async def fake_turn(model, history, tools, emit, on_delta):
        await on_delta("answer")

    with TestClient(main.app) as client:
        agent_wiring.live_text.run_turn, orig = fake_turn, agent_wiring.live_text.run_turn
        try:
            with client.websocket_connect("/ws") as ws:
                for _ in range(10):
                    if ws.receive_json()["t"] == "models":
                        break
                ws.send_json({"t": "new_conversation", "clear_scene": False})
                seen = []
                while not seen or seen[-1] != {"t": "notice", "text": "Nova konverzace"}:
                    seen.append(ws.receive_json())
                assert {"t": "conversation_reset", "clear_scene": False} in seen
                assert seen[-1] == {"t": "notice", "text": "Nova konverzace"}
        finally:
            agent_wiring.live_text.run_turn = orig
