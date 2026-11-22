# backend/tests/test_voice_progress.py
import asyncio

from app.voice.progress import MAX_CHARS, ProgressSpeaker, label_of
from app.voice.relay import Relay
from app.voice.tools import Tool, ToolRegistry, ToolRunner


def run(coro):
    return asyncio.run(coro)


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def speaker(sent, session=True, talking=False, clock=None):
    async def send(text):
        sent.append(text)

    return ProgressSpeaker(send, lambda: session, lambda: talking, clock or Clock())


def test_label_maps_tool_name():
    assert label_of("house_from_sources") == "house from sources"


def test_say_is_rate_limited_to_one_per_six_seconds():
    sent, clock = [], Clock()
    sp = speaker(sent, clock=clock)
    assert run(sp.say("a", "c1")) is True
    assert run(sp.say("b", "c1")) is False
    clock.now += 5.9
    assert run(sp.say("b", "c1")) is False
    clock.now += 0.2
    assert run(sp.say("b", "c1")) is True
    assert sent == ["a", "b"]


def test_at_most_three_per_tool_call():
    sent, clock = [], Clock()
    sp = speaker(sent, clock=clock)
    results = []
    for _ in range(5):
        results.append(run(sp.say("x", "c1")))
        clock.now += 7
    assert results == [True, True, True, False, False]
    assert run(sp.say("y", "c2")) is True  # another call has its own budget


def test_text_is_cut_to_120_chars():
    sent = []
    run(speaker(sent).say("x" * 300))
    assert len(sent[0]) == MAX_CHARS


def test_skipped_while_someone_is_speaking():
    sent = []
    assert run(speaker(sent, talking=True).say("a")) is False
    assert sent == []


def test_dropped_silently_without_session():
    sent = []
    assert run(speaker(sent, session=False).say("a")) is False
    assert sent == []


def test_disabled_by_env(monkeypatch):
    sent = []
    for value in ("0", "false", "off"):
        monkeypatch.setenv("FRIDAY_SPOKEN_PROGRESS", value)
        assert run(speaker(sent).say("a")) is False
    monkeypatch.setenv("FRIDAY_SPOKEN_PROGRESS", "1")
    assert run(speaker(sent).say("a")) is True
    assert sent == ["a"]


def test_send_failure_is_swallowed():
    async def boom(text):
        raise RuntimeError("closed")

    sp = ProgressSpeaker(boom, lambda: True, lambda: False, Clock())
    assert run(sp.say("a")) is False


def test_watch_speaks_at_start_and_once_more_when_slow():
    async def scenario():
        sent, clock = [], Clock()
        sp = speaker(sent, clock=clock)
        async with sp.watch("web_fetch", "c1", slow_after=0.05):
            assert sent == ["Working on web fetch (this may take a moment)"]
            clock.now += 10
            await asyncio.sleep(0.1)
        return sent

    assert run(scenario()) == ["Working on web fetch (this may take a moment)", "Still working on web fetch"]


def test_watch_is_quiet_extra_for_fast_tools():
    async def scenario():
        sent = []
        async with speaker(sent).watch("web_fetch", "c1", slow_after=0.2):
            pass
        await asyncio.sleep(0.25)
        return sent

    assert len(run(scenario())) == 1


def test_relay_someone_speaking_reflects_state_and_open_user_transcript():
    async def scenario():
        async def noop(*_):
            pass

        relay = Relay(noop, noop, lambda: False)
        assert relay.someone_speaking is False
        await relay.set_state("speaking")
        assert relay.someone_speaking is True
        await relay.set_state("listening")
        relay._text["user"] = "hello"
        assert relay.someone_speaking is True
        return True

    assert run(scenario())


def test_long_tool_run_by_runner_triggers_progress():
    from google.genai import types

    async def scenario():
        sent, events, replies = [], [], []

        class Session:
            async def send_tool_response(self, function_responses):
                replies.extend(function_responses)

        async def handler(args):
            return {"ok": True}

        async def emit(event):
            events.append(event)

        registry = ToolRegistry()
        registry.register(Tool("analyze_file", "d", {"type": "object"}, handler, long=True))
        runner = ToolRunner(registry, Session(), emit, None, speaker(sent))
        await runner.handle([types.FunctionCall(id="c1", name="analyze_file", args={})])
        await asyncio.gather(*runner.long_running)
        return sent, replies

    sent, replies = run(scenario())
    assert sent == ["Working on analyze file (this may take a moment)"]
    assert len(replies) == 1
