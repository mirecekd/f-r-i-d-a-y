# backend/tests/test_agent_fallback.py
import asyncio

import httpx
import pytest

from app.agent import fallback
from app.agent.catalog import catalog
from app.agent.fallback import Fallback, is_retryable, ladder
from app.agent.llm import LlmError


def run(coro):
    return asyncio.run(coro)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class HttpError(Exception):
    def __init__(self, status, text="boom"):
        super().__init__(text)
        self.status_code = status


def entry(model_id, provider="litellm", group="g", roles=("agent",)):
    return {"id": model_id, "provider": provider, "label": model_id, "group": group, "roles": list(roles)}


@pytest.fixture(autouse=True)
def fake_catalog(monkeypatch):
    entries = {
        "gemini": [
            entry("gemini-3-pro", "gemini", "google"),
            entry("gemini-3-flash", "gemini", "google"),
            entry("gemini-live", "gemini", "google live", ("chat",)),
        ],
        "litellm": [
            entry("anthropic.claude-big", group="anthropic"),
            entry("anthropic.claude-haiku", group="anthropic"),
            entry("openai.gpt-big", group="openai"),
            entry("openai.gpt-mini", group="openai"),
        ],
    }
    monkeypatch.setattr(catalog, "_entries", {k: (0.0, v) for k, v in entries.items()})


def test_ladder_pinned_first_then_other_provider_cheaper_first_max_three():
    assert ladder("agent", "gemini-3-pro") == [
        "gemini-3-pro",
        "anthropic.claude-haiku",
        "openai.gpt-mini",
        "anthropic.claude-big",
    ]


def test_ladder_is_deterministic_never_has_other_roles_or_duplicates():
    first = ladder("agent", "anthropic.claude-big")
    assert first == ladder("agent", "anthropic.claude-big")
    assert "gemini-live" not in first and len(set(first)) == len(first)
    assert first[0] == "anthropic.claude-big" and len(first) == 4
    assert ladder("chat", "gemini-live") == ["gemini-live"]


def test_ladder_with_pin_outside_catalog_still_starts_with_pin():
    assert ladder("agent", "unknown-model")[0] == "unknown-model"


def test_retryable_classification():
    for e in (HttpError(429), HttpError(408), HttpError(503), TimeoutError(), ConnectionResetError(), httpx.ReadTimeout("t"),
              LlmError("litellm 429: slow down"), LlmError("litellm 502: bad gateway"), RuntimeError("Model is overloaded"),
              RuntimeError("Quota exceeded"), RuntimeError("rate limit hit")):
        assert is_retryable(e), e
    for e in (HttpError(400), HttpError(401), HttpError(403), LlmError("litellm 400: bad request"),
              LlmError("litellm 401: nope"), RuntimeError("content blocked by safety filter"), ValueError("x")):
        assert not is_retryable(e), e


def test_falls_back_on_retryable_and_announces_once_per_switch():
    fb, notices, tried = Fallback(Clock()), [], []

    async def note(text):
        notices.append(text)

    async def do(model):
        tried.append(model)
        if model == "gemini-3-pro":
            raise HttpError(429)
        return model

    assert run(fb.call("agent", "gemini-3-pro", do, note)) == "anthropic.claude-haiku"
    assert run(fb.call("agent", "gemini-3-pro", do, note)) == "anthropic.claude-haiku"
    assert notices == ["Model gemini-3-pro is rate limited, using anthropic.claude-haiku"]
    assert tried == ["gemini-3-pro", "anthropic.claude-haiku", "anthropic.claude-haiku"]  # second call skips the cooled model


def test_non_retryable_error_is_raised_without_trying_alternates():
    fb, tried = Fallback(Clock()), []

    async def do(model):
        tried.append(model)
        raise HttpError(400, "bad request")

    with pytest.raises(HttpError):
        run(fb.call("agent", "gemini-3-pro", do))
    assert tried == ["gemini-3-pro"]
    assert fb.cooldowns.active("gemini-3-pro") is False


def test_cooldown_expires_and_grows_on_repeats():
    clock = Clock()
    fb = Fallback(clock)
    fb.cooldowns.fail("m")
    assert fb.cooldowns.active("m")
    clock.now += 59
    assert fb.cooldowns.active("m")
    clock.now += 2
    assert not fb.cooldowns.active("m")
    fb.cooldowns.fail("m")
    clock.now += 61
    assert fb.cooldowns.active("m")  # second strike: 120 s
    for _ in range(6):
        fb.cooldowns.fail("m")
    clock.now += 301
    assert not fb.cooldowns.active("m")  # capped at 5 minutes


def test_pinned_model_returns_after_cooldown_and_next_switch_is_announced_again():
    clock, notices = Clock(), []
    fb = Fallback(clock)
    failing = {"on": True}

    async def note(text):
        notices.append(text)

    async def do(model):
        if model == "gemini-3-pro" and failing["on"]:
            raise HttpError(429)
        return model

    assert run(fb.call("agent", "gemini-3-pro", do, note)) == "anthropic.claude-haiku"
    clock.now += 61
    failing["on"] = False
    assert run(fb.call("agent", "gemini-3-pro", do, note)) == "gemini-3-pro"
    failing["on"] = True
    clock.now += 400
    assert run(fb.call("agent", "gemini-3-pro", do, note)) == "anthropic.claude-haiku"
    assert len(notices) == 2


def test_all_models_failing_raises_the_last_error():
    fb, tried = Fallback(Clock()), []

    async def do(model):
        tried.append(model)
        raise HttpError(503, f"down {model}")

    with pytest.raises(HttpError, match="down anthropic.claude-big") as err:
        run(fb.call("agent", "gemini-3-pro", do))
    assert err.value.status_code == 503
    assert len(tried) == 4 and tried[-1] == "anthropic.claude-big"


def test_no_fallback_once_text_was_streamed():
    fb = Fallback(Clock())

    async def do(model):
        raise HttpError(429)

    with pytest.raises(HttpError):
        run(fb.call("agent", "gemini-3-pro", do, can_retry=lambda: False))


def test_module_level_call_with_fallback_uses_shared_state():
    async def do(model):
        return model

    assert run(fallback.call_with_fallback("agent", "gemini-3-pro", do)) == "gemini-3-pro"
