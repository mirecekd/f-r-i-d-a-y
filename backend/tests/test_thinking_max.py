# backend/tests/test_thinking_max.py
"""The `max` thinking level per path: Live and Gemini clamp to high, LiteLLM uses the learned/advertised strongest effort."""

import asyncio
import json

import httpx
import pytest
from google.genai import types

from app.agent import llm, prefs, thinking, thinking_litellm
from app.agent.catalog import catalog
from app.agent.catalog_litellm import filter_model_info

LEVEL = types.ThinkingLevel
REAL_CLIENT = httpx.AsyncClient


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.delenv("FRIDAY_THINKING", raising=False)
    monkeypatch.setattr(thinking_litellm, "REJECTED", set())
    monkeypatch.setattr(thinking_litellm, "CEILING", {})
    monkeypatch.setattr(thinking.AGENT, "bad_levels", {k: set(v) for k, v in thinking.AGENT.bad_levels.items()})
    monkeypatch.setattr(thinking.LIVE, "bad_levels", {k: set(v) for k, v in thinking.LIVE.bad_levels.items()})


def test_max_is_the_fifth_level_and_default_stays_high():
    assert thinking.LEVELS == ("minimal", "low", "medium", "high", "max") and thinking.DEFAULT_LEVEL == "high"
    prefs.save_thinking("max")
    assert thinking.current() == "max"


def test_voice_clamps_max_to_high():
    cfg = thinking.live_config("gemini-3.8-live-extended-thinking", "max")
    assert cfg is not None and cfg.thinking_level == LEVEL.HIGH


def test_gemini_3x_agent_max_is_high_and_25_is_dynamic_budget():
    cfg = thinking.agent_config("gemini-3.8-flash", "max")
    assert cfg is not None and cfg.thinking_level == LEVEL.HIGH
    old = thinking.agent_config("gemini-2.5-pro", "max")
    assert old is not None and old.thinking_budget == -1 and old.thinking_level is None


def test_gemini_4_neon_is_high_only():
    for level in ("minimal", "low", "medium", "max"):
        cfg = thinking.agent_config("gemini-4-neon", level)
        assert cfg is not None and cfg.thinking_level == LEVEL.HIGH


def test_effort_mapping_for_max_uses_catalog_top_then_learned_ceiling():
    assert thinking_litellm.effort("m", "max", "max") == "max"
    assert thinking_litellm.effort("m", "max", "xhigh") == "xhigh"
    assert thinking_litellm.effort("m", "max", None) == "high"  # unknown model: safe
    assert thinking_litellm.effort("m", "medium", "max") == "medium"
    thinking_litellm.CEILING["m"] = "xhigh"
    assert thinking_litellm.effort("m", "max", "max") == "xhigh"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        ("Invalid reasoning_effort: 'x'. Must be one of: 'minimal', 'low', 'medium', 'high', 'xhigh'", {"minimal", "low", "medium", "high", "xhigh"}),
        ("Invalid value. Supported values are: 'none', 'low', 'medium', 'high', 'xhigh', and 'max'.", {"low", "medium", "high", "xhigh", "max"}),
        ("reasoning_effort must be one of low, medium, high, xhigh", {"low", "medium", "high", "xhigh"}),
        ("'reasoning_effort' value 'max' is not supported by this model", set()),
    ],
)
def test_allowed_values_parsed_from_400_text(error, expected):
    assert thinking_litellm.allowed_values(error) == expected


def test_learn_picks_highest_allowed_value():
    thinking_litellm.learn("m", "max", "must be one of low, medium, high, xhigh")
    assert thinking_litellm.CEILING["m"] == "xhigh" and "m" not in thinking_litellm.REJECTED


def test_learn_without_a_list_steps_down_then_gives_up():
    thinking_litellm.learn("m", "max", "value is not supported")
    assert thinking_litellm.CEILING["m"] == "xhigh"
    thinking_litellm.learn("m", "xhigh", "value is not supported")
    assert thinking_litellm.CEILING["m"] == "high"
    thinking_litellm.learn("m", "high", "no")
    assert "m" in thinking_litellm.REJECTED


def test_top_effort_from_model_info():
    assert thinking_litellm.top_effort({"supports_max_reasoning_effort": True, "supports_xhigh_reasoning_effort": True}) == "max"
    assert thinking_litellm.top_effort({"supports_xhigh_reasoning_effort": True}) == "xhigh"
    assert thinking_litellm.top_effort({"reasoning_effort_levels": ["low", "high", "xhigh", "max"]}) == "max"
    assert thinking_litellm.top_effort({"reasoning_effort_levels": ["low", "high"]}) is None
    assert thinking_litellm.top_effort({}) is None


def test_catalog_carries_max_effort_for_reasoning_models_only():
    def item(name, **info):
        return {"model_name": name, "model_info": {"mode": "chat", "supports_function_calling": True, **info}}

    entries = filter_model_info(
        {"data": [item("a", supports_reasoning=True, supports_max_reasoning_effort=True), item("b", supports_reasoning=True), item("c", supports_max_reasoning_effort=True)]}
    )
    caps = {e["id"]: e["caps"] for e in entries}
    labels = {e["id"]: e["label"] for e in entries}
    assert labels["a"] == "a (max thinking)" and labels["b"] == "b" and labels["c"] == "c"
    assert caps["a"]["max_effort"] == "max" and "max_effort" not in caps["b"] and "max_effort" not in caps["c"]


def run(monkeypatch, handler, entry_caps):
    entry = {"id": "r1", "provider": "litellm", "label": "r", "group": "g", "roles": ["agent"], "caps": entry_caps}
    monkeypatch.setattr(catalog, "_entries", {"litellm": (0.0, [entry])})
    monkeypatch.setenv("LITELLM_BASE_URL", "http://proxy.test")
    monkeypatch.setenv("LITELLM_API_KEY", "k")
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handler), **kw))
    return asyncio.run(llm.chat_litellm("r1", [{"role": "user", "content": "x"}], []))


def test_litellm_max_sends_the_advertised_top_effort(monkeypatch):
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, content=b"data: [DONE]\n\n")

    prefs.save_thinking("max")
    run(monkeypatch, handler, {"reasoning": True, "max_effort": "max"})
    assert bodies[0]["reasoning_effort"] == "max" and "thinking" not in bodies[0]


def test_litellm_fake_400_lists_allowed_values_and_retry_uses_highest(monkeypatch):
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        if bodies[-1]["reasoning_effort"] in ("max", "xhigh") and bodies[-1]["reasoning_effort"] != "xhigh":
            return httpx.Response(400, text="Invalid reasoning_effort 'max'. Must be one of: 'low', 'medium', 'high', 'xhigh'")
        return httpx.Response(200, content=b"data: [DONE]\n\n")

    prefs.save_thinking("max")
    run(monkeypatch, handler, {"reasoning": True, "max_effort": "max"})
    run(monkeypatch, handler, {"reasoning": True, "max_effort": "max"})
    assert [b["reasoning_effort"] for b in bodies] == ["max", "xhigh", "xhigh"]  # learned once, kept for the next call


def test_litellm_unknown_model_without_catalog_top_sends_high(monkeypatch):
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, content=b"data: [DONE]\n\n")

    prefs.save_thinking("max")
    run(monkeypatch, handler, {"reasoning": True})
    assert bodies[0]["reasoning_effort"] == "high"
