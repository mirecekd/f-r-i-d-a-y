# backend/tests/test_agent_catalog.py
import asyncio
from types import SimpleNamespace

import httpx

from app.agent import catalog as cat

LITELLM_MODELS = {
    "data": [
        {"id": "eu.anthropic.claude-opus-5", "mode": "chat"},
        {"id": "global.openai.gpt-6-sol"},
        {"id": "cohere.rerank-v3-5:0", "mode": "rerank"},
        {"id": "cohere.embed-multilingual-v3"},
        {"id": "stability.sd3-5-large-v1:0"},
        {"id": "us.amazon.nova-2-multimodal-embeddings-v1:0"},
        {"id": "eu.google.gemma-4-31b", "mode": "chat"},
    ]
}


def info(
    name: str,
    mode: str | None = "chat",
    tools: bool | None = True,
    vision: bool | None = None,
    reasoning: bool | None = None,
):
    return {
        "model_name": name,
        "model_info": {
            "mode": mode,
            "supports_function_calling": tools,
            "supports_vision": vision,
            "supports_reasoning": reasoning,
        },
    }


LITELLM_INFO = {
    "data": [
        info("eu.anthropic.claude-opus-5", vision=True, reasoning=True),
        info("eu.mistral.mistral-7b-instruct-v0:2", tools=None),
        info("eu.mistral.pixtral-large-2502-v1:0"),
        info("cohere.rerank-v3-5:0", mode="rerank", tools=None),
        info("global.cohere.embed-v4:0", mode="embedding", tools=None),
        info("global.some.image-gen", tools=True),
        info("eu.google.gemma-4-31b", mode=None, tools=None),
    ]
}


def m(name, display, actions, thinking=None):
    return SimpleNamespace(name=name, display_name=display, supported_actions=actions, thinking=thinking)


GEMINI_MODELS = [
    m("models/gemini-3.8-live", "Gemini 3.8 Live", ["bidiGenerateContent"]),
    m("models/gemini-3.8-live-extended-thinking", "Gemini 3.8 Live Extended Thinking", ["bidiGenerateContent"]),
    m("models/gemini-3.1-flash-live-preview", "Gemini 3.1 Flash Live Preview", ["bidiGenerateContent"]),
    m("models/gemini-2.5-flash-native-audio-latest", "Native Audio", ["bidiGenerateContent"]),
    m("models/gemini-3.5-transcribe-live", "Transcribe Live", ["bidiGenerateContent"]),
    m("models/gemini-3.5-live-translate-preview", "Translate", ["bidiGenerateContent"]),
    m("models/genie-4", "Genie 4", ["bidiGenerateContent"]),
    m("models/gemini-robotics-er-2-streaming-preview", "Robotics", ["bidiGenerateContent"]),
    m("models/gemini-3.5-flash", "Gemini 3.5 Flash", ["generateContent"], thinking=True),
    m("models/gemini-3.5-flash-lite", "Gemini 3.5 Flash Lite", ["generateContent"]),
    m("models/gemini-2.5-flash-preview-tts", "TTS", ["generateContent"]),
    m("models/gemini-3-pro-image", "Nano Banana Pro", ["generateContent"]),
    m("models/embedding-001", "Emb", ["embedContent"]),
    m("models/gemma-4-31b-it", "Gemma 4 31B IT", ["generateContent"]),
    m("models/aqa", "AQA", ["generateAnswer"]),
]


def test_filter_live_keeps_only_bidi_conversational_models_with_labels():
    entries = cat.gemini.filter_live(GEMINI_MODELS)
    assert sorted(e["id"] for e in entries) == [
        "gemini-2.5-flash-native-audio-latest",
        "gemini-3.1-flash-live-preview",
        "gemini-3.8-live",
        "gemini-3.8-live-extended-thinking",
    ]
    assert all(e["roles"] == ["chat"] for e in entries)
    by_id = {e["id"]: e["label"] for e in entries}
    assert "async only, no scheduling" in by_id["gemini-3.8-live-extended-thinking"]
    assert "legacy: no async tools" in by_id["gemini-3.1-flash-live-preview"]
    assert by_id["gemini-3.8-live"] == "Gemini 3.8 Live"


def test_filter_text_gemini_for_agent_role():
    entries = cat.gemini.filter_text(GEMINI_MODELS)
    assert [e["id"] for e in entries] == ["gemini-3.5-flash", "gemini-3.5-flash-lite"]
    assert all(e["roles"] == ["agent"] and e["caps"]["tools"] for e in entries)
    assert entries[0]["caps"]["reasoning"] is True


def test_filter_litellm_models_fallback_drops_non_chat_and_groups():
    entries = cat.litellm.filter_models(LITELLM_MODELS)
    assert [e["id"] for e in entries] == ["eu.anthropic.claude-opus-5", "eu.google.gemma-4-31b", "global.openai.gpt-6-sol"]
    assert entries[0] == {
        "id": "eu.anthropic.claude-opus-5",
        "provider": "litellm",
        "label": "claude-opus-5 (eu)",
        "group": "anthropic",
        "roles": ["agent"],
    }


def test_filter_model_info_requires_function_calling_and_reports_caps():
    entries = cat.litellm.filter_model_info(LITELLM_INFO)
    assert [e["id"] for e in entries] == ["eu.anthropic.claude-opus-5", "eu.mistral.pixtral-large-2502-v1:0"]
    assert entries[0]["caps"] == {"tools": True, "vision": True, "reasoning": True}
    assert entries[1]["caps"] == {"tools": True, "vision": False, "reasoning": False}


def run_fetch(handler):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await cat.fetch_litellm(client)

    return asyncio.run(run())


def test_fetch_litellm_prefers_model_info_with_bearer(monkeypatch):
    monkeypatch.setenv("LITELLM_BASE_URL", "http://litellm.test/v1")
    monkeypatch.setenv("LITELLM_API_KEY", "k-test")
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((str(request.url), request.headers["authorization"]))
        return httpx.Response(200, json=LITELLM_INFO)

    assert len(run_fetch(handler)) == 2
    assert seen == [("http://litellm.test/v1/model/info", "Bearer k-test")]


def test_fetch_litellm_falls_back_to_models_when_info_denied(monkeypatch):
    monkeypatch.setenv("LITELLM_BASE_URL", "http://litellm.test/v1")
    monkeypatch.setenv("LITELLM_API_KEY", "k-test")
    paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("/model/info"):
            return httpx.Response(403, json={})
        return httpx.Response(200, json=LITELLM_MODELS)

    assert len(run_fetch(handler)) == 3
    assert paths == ["/v1/model/info", "/v1/models"]


def test_cache_ttl_merge_and_failed_provider_retried():
    now = [0.0]
    calls = {"gemini": 0, "litellm": 0}

    async def gemini():
        calls["gemini"] += 1
        return [{"id": "g1", "provider": "gemini", "label": "G1", "group": "google", "roles": ["agent"]}]

    async def litellm():
        calls["litellm"] += 1
        if calls["litellm"] == 1:
            raise RuntimeError("down")
        return [{"id": "l1", "provider": "litellm", "label": "L1", "group": "x", "roles": ["agent"]}]

    cache = cat.CatalogCache({"gemini": gemini, "litellm": litellm}, ttl=600, clock=lambda: now[0])
    assert [e["id"] for e in asyncio.run(cache.get())] == ["g1"]
    assert [e["id"] for e in asyncio.run(cache.get())] == ["g1", "l1"]  # failed provider retried at once
    now[0] = 599
    asyncio.run(cache.get())
    assert calls == {"gemini": 1, "litellm": 2}
    now[0] = 601
    asyncio.run(cache.get())
    assert calls == {"gemini": 2, "litellm": 3}
    assert cache.provider_of("l1") == "litellm" and cache.provider_of("nope") is None
    assert cache.has_role("l1", "agent") and not cache.has_role("l1", "chat")
