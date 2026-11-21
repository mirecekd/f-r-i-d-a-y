# backend/tests/test_approval.py
"""Approvals: request/answer, timeout, disconnect, session memory, masking, and ToolRunner gating."""

import asyncio
from typing import Any

from google.genai import types

from app.approval import Approvals, mask_args
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


def test_mask_args_masks_secrets_and_truncates():
    out = mask_args({"api_key": "k", "auth_" + "TOKEN": "t", "nested": {"password": "p", "ok": 1}, "text": "x" * 500, "n": 3})
    assert out["api_key"] == "***" and out["auth_TOKEN"] == "***"
    assert out["nested"] == {"password": "***", "ok": 1}
    assert len(out["text"]) < 300 and out["n"] == 3


def test_allow_resolves_true_and_emits_request():
    async def go():
        sink = Sink()
        ap = Approvals(sink)
        task = asyncio.create_task(ap.ask("demo", "do it", {"secret": "s", "a": 1}, timeout=5))
        await until(lambda: sink.kinds("confirm_request"))
        req = sink.kinds("confirm_request")[0]
        assert req["tool"] == "demo" and req["summary"] == "do it" and req["expires_in"] == 5
        assert req["args"] == {"secret": "***", "a": 1}
        ap.resolve({"t": "confirm", "id": req["id"], "allow": True})
        assert await task is True
        assert not sink.kinds("confirm_closed")

    asyncio.run(go())


def test_deny_and_unknown_id():
    async def go():
        sink = Sink()
        ap = Approvals(sink)
        task = asyncio.create_task(ap.ask("demo", "s", {}))
        await until(lambda: sink.kinds("confirm_request"))
        ap.resolve({"t": "confirm", "id": "nope", "allow": True})
        assert not task.done()
        ap.resolve({"t": "confirm", "id": sink.kinds("confirm_request")[0]["id"], "allow": False})
        assert await task is False

    asyncio.run(go())


def test_timeout_denies_and_emits_closed():
    async def go():
        sink = Sink()
        assert await Approvals(sink).ask("demo", "s", {}, timeout=0.05) is False
        closed = sink.kinds("confirm_closed")
        assert closed[0]["reason"] == "timeout" and closed[0]["id"] == sink.kinds("confirm_request")[0]["id"]

    asyncio.run(go())


def test_close_denies_pending():
    async def go():
        sink = Sink()
        ap = Approvals(sink)
        task = asyncio.create_task(ap.ask("demo", "s", {}))
        await until(lambda: sink.kinds("confirm_request"))
        ap.close()
        assert await task is False

    asyncio.run(go())


def test_emit_failure_denies():
    async def go():
        async def broken(_msg: dict) -> None:
            raise RuntimeError("socket closed")

        assert await Approvals(broken).ask("demo", "s", {}) is False

    asyncio.run(go())


def test_remember_session_skips_next_prompt_and_is_per_tool():
    async def go():
        sink = Sink()
        ap = Approvals(sink)
        task = asyncio.create_task(ap.ask("demo", "s", {}))
        await until(lambda: sink.kinds("confirm_request"))
        ap.resolve({"t": "confirm", "id": sink.kinds("confirm_request")[0]["id"], "allow": True, "remember": "session"})
        assert await task is True
        assert await ap.ask("demo", "s", {}) is True
        assert len(sink.kinds("confirm_request")) == 1
        other = asyncio.create_task(ap.ask("other", "s", {}, timeout=0.05))
        assert await other is False
        assert len(sink.kinds("confirm_request")) == 2

    asyncio.run(go())


def test_remember_once_and_deny_do_not_stick():
    async def go():
        sink = Sink()
        ap = Approvals(sink)
        for answer in ({"allow": True, "remember": "once"}, {"allow": False, "remember": "session"}):
            task = asyncio.create_task(ap.ask("demo", "s", {}))
            seen = len(sink.kinds("confirm_request"))
            await until(lambda n=seen: len(sink.kinds("confirm_request")) > n)
            ap.resolve({"t": "confirm", "id": sink.kinds("confirm_request")[-1]["id"], **answer})
            await task
        assert len(sink.kinds("confirm_request")) == 2

    asyncio.run(go())


class FakeLive:
    def __init__(self) -> None:
        self.responses: list[Any] = []

    async def send_tool_response(self, function_responses):
        self.responses.extend(function_responses)


def runner_with_risky(sink: Sink, approvals: Approvals | None):
    ran: list[dict] = []

    async def handler(args: dict) -> dict:
        ran.append(args)
        return {"ok": True}

    registry = ToolRegistry()
    registry.register(Tool("danger", "d", {"type": "object"}, handler, risky=True, confirm_summary=lambda a: f"danger {a}"))
    registry.register(Tool("safe", "s", {"type": "object"}, handler))
    return ToolRunner(registry, FakeLive(), sink, approvals), ran


def call(name: str) -> types.FunctionCall:
    return types.FunctionCall(id="c1", name=name, args={"x": 1})


def test_runner_risky_allowed_runs_and_denied_does_not():
    async def go():
        sink = Sink()
        ap = Approvals(sink)
        runner, ran = runner_with_risky(sink, ap)
        task = asyncio.create_task(runner.handle([call("danger")]))
        await until(lambda: sink.kinds("confirm_request"))
        req = sink.kinds("confirm_request")[0]
        assert req["summary"] == "danger {'x': 1}"
        ap.resolve({"t": "confirm", "id": req["id"], "allow": False})
        await task
        assert not ran
        assert runner.session.responses[0].response == {"error": "denied by user"}

        task = asyncio.create_task(runner.handle([call("danger")]))
        await until(lambda: len(sink.kinds("confirm_request")) == 2)
        ap.resolve({"t": "confirm", "id": sink.kinds("confirm_request")[1]["id"], "allow": True})
        await task
        assert ran == [{"x": 1}]
        assert runner.session.responses[1].response == {"ok": True}

    asyncio.run(go())


def test_runner_safe_tool_never_asks_and_risky_without_approvals_is_denied():
    async def go():
        sink = Sink()
        runner, ran = runner_with_risky(sink, Approvals(sink))
        await runner.handle([call("safe")])
        assert ran and not sink.kinds("confirm_request")
        runner, ran = runner_with_risky(sink, None)
        await runner.handle([call("danger")])
        assert len(ran) == 0 and runner.session.responses[0].response == {"error": "denied by user"}

    asyncio.run(go())
