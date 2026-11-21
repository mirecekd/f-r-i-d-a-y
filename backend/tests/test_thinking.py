# backend/tests/test_thinking.py
"""Unified thinking level: prefs, per-model fallback tables, request building on every path, protocol."""

import asyncio
import json

import httpx
import pytest
from google.genai import errors, types

from app.agent import llm, llm_gemini, prefs, thinking, thinking_litellm
from app.agent.catalog import catalog
from app.voice import ToolRegistry, session

LEVEL = types.ThinkingLevel
REAL_CLIENT = httpx.AsyncClient


@pytest.fixture(autouse=True)
def clean_tables(monkeypatch):
    monkeypatch.delenv("FRIDAY_THINKING", raising=False)
    for table in (thinking.LIVE, thinking.AGENT):
        monkeypatch.setattr(table, "no_config", set(table.no_config))
        monkeypatch.setattr(table, "budget_only", set())
        monkeypatch.setattr(table, "bad_levels", {k: set(v) for k, v in table.bad_levels.items()})
    monkeypatch.setattr(thinking_litellm, "REJECTED", set())
    monkeypatch.setattr(thinking_litellm, "CEILING", {})


def test_default_is_high_and_pin_and_env_fallback(monkeypatch):
    assert thinking.current() == "high" and prefs.thinking() is None
    monkeypatch.setenv("FRIDAY_THINKING", "low")
    assert thinking.current() == "low"
    prefs.save_thinking("minimal")
    assert thinking.current() == "minimal" and prefs.load()["chat_model"] is None
    monkeypatch.setenv("FRIDAY_THINKING", "bogus")
    prefs.save_thinking("medium")
    assert thinking.current() == "medium"


def test_live_config_per_model_table():
    assert thinking.live_config("gemini-3.8-live") is None  # probed: rejects any thinking config
    cfg = thinking.live_config("gemini-3.1-flash-live-preview")
    assert cfg and cfg.thinking_level == LEVEL.HIGH and cfg.include_thoughts is False
    ext = thinking.live_config("gemini-3.8-live-extended-thinking", "minimal")
    assert ext and ext.thinking_level == LEVEL.LOW  # MINIMAL is rejected there: next level up


def test_live_build_config_carries_level(monkeypatch):
    monkeypatch.setenv("GEMINI_LIVE_MODEL", "gemini-3.8-live-extended-thinking")
    prefs.save_thinking("medium")
    cfg = session.build_config(ToolRegistry())
    assert cfg.thinking_config and cfg.thinking_config.thinking_level == LEVEL.MEDIUM
    monkeypatch.setenv("GEMINI_LIVE_MODEL", "gemini-3.8-live")
    assert session.build_config(ToolRegistry()).thinking_config is None


def test_learn_from_live_errors():
    assert thinking.LIVE.learn("m", "1007 None. Thinking level MINIMAL is not supported for this model.")
    assert thinking.live_config("m", "minimal").thinking_level == LEVEL.LOW  # type: ignore[union-attr]
    assert thinking.LIVE.learn("n", "1007 None. Thinking level is not supported for this model.")
    assert thinking.live_config("n") is None
    assert not thinking.LIVE.learn("n", "1007 None. Unsupported language code")
    assert thinking.LIVE.learn("gemini-3.8-live", "1007 None. Thinking level must be specified for this model.")
    assert thinking.live_config("gemini-3.8-live") is not None  # stale table entry dropped


def test_agent_config_levels_and_budgets():
    flash3 = thinking.agent_config("gemini-3.5-flash", "low")
    assert flash3 and flash3.thinking_level == LEVEL.LOW and flash3.thinking_budget is None
    assert thinking.agent_config("gemini-3.5-flash", "minimal").thinking_level == LEVEL.MINIMAL  # type: ignore[union-attr]
    assert thinking.agent_config("gemini-flash-latest", "minimal").thinking_level == LEVEL.LOW  # type: ignore[union-attr]
    for level, budget in (("high", -1), ("medium", 8192), ("low", 1024), ("minimal", 0)):
        cfg = thinking.agent_config("gemini-2.5-flash", level)
        assert cfg and cfg.thinking_budget == budget and cfg.thinking_level is None
    assert thinking.agent_config("gemini-2.5-flash-lite", "minimal").thinking_budget == 128  # type: ignore[union-attr]


def test_agent_learns_budget_only_model():
    assert thinking.AGENT.learn("gemini-9-x", "400 Thinking level is not supported for this model.")
    cfg = thinking.agent_config("gemini-9-x", "medium")
    assert cfg and cfg.thinking_budget == 8192


class FakeModels:
    def __init__(self, fail_first: list[str]):
        self.fail_first = fail_first
        self.configs: list[types.GenerateContentConfig] = []

    async def generate_content_stream(self, model, contents, config):
        self.configs.append(config)
        if self.fail_first:
            raise errors.APIError(400, {"error": {"message": self.fail_first.pop(0)}})

        async def empty():
            if False:
                yield None

        return empty()


def test_chat_gemini_builds_config_and_retries_once_with_learned_budget(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k-test")
    fake = FakeModels(["Thinking level is not supported for this model."])

    class FakeClient:
        def __init__(self, **_):
            self.aio = type("Aio", (), {"models": fake})()

    monkeypatch.setattr(llm_gemini.genai, "Client", FakeClient)
    prefs.save_thinking("low")
    asyncio.run(llm_gemini.chat_gemini("gemini-9-x", [{"role": "user", "content": "x"}], []))
    first, second = fake.configs
    assert first.thinking_config and first.thinking_config.thinking_level == LEVEL.LOW
    assert second.thinking_config and second.thinking_config.thinking_budget == 1024


def litellm_run(monkeypatch, handler, model="r1"):
    monkeypatch.setenv("LITELLM_BASE_URL", "http://litellm.test/v1")
    monkeypatch.setenv("LITELLM_API_KEY", "k-test")
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handler), **kw))
    return asyncio.run(llm.chat_litellm(model, [{"role": "user", "content": "x"}], []))


def with_caps(monkeypatch, reasoning: bool):
    entry = {"id": "r1", "provider": "litellm", "label": "r", "group": "g", "roles": ["agent"], "caps": {"reasoning": reasoning}}
    monkeypatch.setattr(catalog, "_entries", {"litellm": (0.0, [entry])})


def test_litellm_sends_reasoning_effort_only_for_reasoning_models(monkeypatch):
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, content=b"data: [DONE]\n\n")

    prefs.save_thinking("minimal")
    with_caps(monkeypatch, True)
    litellm_run(monkeypatch, handler)
    with_caps(monkeypatch, False)
    litellm_run(monkeypatch, handler)
    assert bodies[0]["reasoning_effort"] == "low"  # minimal maps to low
    assert "reasoning_effort" not in bodies[1]
    assert [thinking.litellm_effort("r1", None, x) for x in thinking.LEVELS] == ["low", "low", "medium", "high", "high"]


def test_litellm_400_retries_once_without_effort_and_remembers(monkeypatch):
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        if "reasoning_effort" in bodies[-1]:
            return httpx.Response(400, text="reasoning_effort not supported")
        return httpx.Response(200, content=b"data: [DONE]\n\n")

    with_caps(monkeypatch, True)
    litellm_run(monkeypatch, handler)
    litellm_run(monkeypatch, handler)
    assert ["reasoning_effort" in b for b in bodies] == [True, False, False]
    assert "r1" in thinking_litellm.REJECTED


def test_other_litellm_400_without_effort_is_still_an_error(monkeypatch):
    with_caps(monkeypatch, False)
    with pytest.raises(llm.LlmError, match="400"):
        litellm_run(monkeypatch, lambda r: httpx.Response(400, text="bad"))


def test_live_text_build_config_carries_level():
    from app.agent import live_text

    prefs.save_thinking("low")
    cfg = live_text.build_config("gemini-3.1-flash-live-preview", {})
    assert cfg.thinking_config and cfg.thinking_config.thinking_level == LEVEL.LOW
    assert live_text.build_config("gemini-3.8-live", {}).thinking_config is None
