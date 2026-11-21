# backend/tests/test_agent_loop.py
import asyncio
import json

from app.agent import loop
from app.agent.draw import make_draw_tool
from app.voice.tools import Tool


class FakeModel:
    """Replaces llm.chat: scripted replies, records the messages it was shown."""

    def __init__(self, replies):
        self.replies, self.seen = list(replies), []

    async def __call__(self, model, messages, tools, on_delta=None):
        self.seen.append((model, [dict(m) for m in messages], [t["function"]["name"] for t in tools]))
        return self.replies.pop(0)


def call(i, name="fake", **args):
    return {"id": f"c{i}", "name": name, "args": args}


def fake_tool(log):
    async def handler(args):
        log.append(args)
        return {"done": args["n"]}

    return Tool("fake", "fake tool", {"type": "object", "properties": {"n": {"type": "integer"}}}, handler)


def run(coro):
    return asyncio.run(coro)


def test_loop_calls_fake_tool_twice_then_answers(monkeypatch):
    model = FakeModel(
        [
            {"text": "", "tool_calls": [call(1, n=1)]},
            {"text": "", "tool_calls": [call(2, n=2)]},
            {"text": "all done", "tool_calls": []},
        ]
    )
    monkeypatch.setattr(loop.llm, "chat", model)
    handled, events = [], []

    async def emit(ev):
        events.append(ev)

    messages = [{"role": "user", "content": "draw"}]
    out = run(loop.run_agent("m", messages, {"fake": fake_tool(handled)}, emit))
    assert out == "all done"
    assert handled == [{"n": 1}, {"n": 2}]
    assert [(e["status"], e["id"]) for e in events] == [("start", "c1"), ("ok", "c1"), ("start", "c2"), ("ok", "c2")]
    assert [m["role"] for m in messages] == ["user", "assistant", "tool", "assistant", "tool", "assistant"]
    assert json.loads(messages[2]["content"]) == {"done": 1}
    assert model.seen[0][2] == ["fake"]


def test_loop_reports_unknown_tool_and_tool_exception(monkeypatch):
    async def boom(args):
        raise ValueError("nope")

    model = FakeModel(
        [
            {"text": "", "tool_calls": [call(1, name="missing"), call(2, name="boom")]},
            {"text": "sorry", "tool_calls": []},
        ]
    )
    monkeypatch.setattr(loop.llm, "chat", model)
    events = []

    async def emit(ev):
        events.append(ev)

    messages = [{"role": "user", "content": "x"}]
    run(loop.run_agent("m", messages, {"boom": Tool("boom", "b", {"type": "object"}, boom)}, emit))
    results = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
    assert "unknown tool" in results[0]["error"] and "ValueError: nope" in results[1]["error"]
    assert [e["status"] for e in events if e["status"] != "start"] == ["error", "error"]


def test_loop_stops_after_max_rounds(monkeypatch):
    model = FakeModel([{"text": "", "tool_calls": [call(i, n=i)]} for i in range(20)])
    monkeypatch.setattr(loop.llm, "chat", model)
    handled = []

    async def emit(ev):
        pass

    out = run(loop.run_agent("m", [{"role": "user", "content": "x"}], {"fake": fake_tool(handled)}, emit))
    assert len(handled) == loop.MAX_ROUNDS == 8
    assert "8 tool rounds" in out


def test_draw_tool_is_long_when_idle_and_runs_agent_with_pinned_model(monkeypatch):
    model = FakeModel([{"text": "", "tool_calls": [call(1, n=7)]}, {"text": "drew it", "tool_calls": []}])
    monkeypatch.setattr(loop.llm, "chat", model)
    handled = []

    async def emit(ev):
        pass

    tool = make_draw_tool(lambda: "pinned-model", lambda: {"fake": fake_tool(handled)}, emit)
    assert tool.name == "draw" and tool.long and tool.scheduling == "WHEN_IDLE"
    assert run(tool.handler({"request": "a red cube"})) == {"ok": True, "summary": "drew it"}
    assert handled == [{"n": 7}]
    assert model.seen[0][0] == "pinned-model"
    assert model.seen[0][1][1] == {"role": "user", "content": "a red cube"}
    assert run(tool.handler({"request": " "})) == {"error": "request is empty"}
