# backend/tests/test_agent_llm.py
import asyncio
import json

import httpx
import pytest

from app.agent import llm
from app.agent.catalog import catalog


def sse(*chunks: dict) -> bytes:
    return ("".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n").encode()


def patch_client(monkeypatch, handler):
    real = httpx.AsyncClient
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))


def test_chat_litellm_streams_text_and_assembles_tool_calls(monkeypatch):
    monkeypatch.setenv("LITELLM_BASE_URL", "http://litellm.test/v1")
    monkeypatch.setenv("LITELLM_API_KEY", "k-test")
    body = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body.update(json.loads(request.content))
        return httpx.Response(
            200,
            content=sse(
                {"choices": [{"delta": {"content": "Hel"}}]},
                {"choices": [{"delta": {"content": "lo"}}]},
                {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "echo", "arguments": '{"te'}}]}}]},
                {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": 'xt": "hi"}'}}]}}]},
            ),
        )

    patch_client(monkeypatch, handler)
    deltas: list[str] = []

    async def on_delta(t: str) -> None:
        deltas.append(t)

    tools = [{"type": "function", "function": {"name": "echo", "parameters": {"type": "object"}}}]
    result = asyncio.run(llm.chat_litellm("m1", [{"role": "user", "content": "x"}], tools, on_delta))
    assert result == {"text": "Hello", "tool_calls": [{"id": "c1", "name": "echo", "args": {"text": "hi"}}]}
    assert deltas == ["Hel", "lo"]
    assert body["model"] == "m1" and body["stream"] is True and body["tools"] == tools


def test_chat_litellm_http_error_is_llm_error(monkeypatch):
    monkeypatch.setenv("LITELLM_BASE_URL", "http://litellm.test/v1")
    monkeypatch.setenv("LITELLM_API_KEY", "k-test")
    patch_client(monkeypatch, lambda r: httpx.Response(400, text="bad model"))
    with pytest.raises(llm.LlmError, match="400"):
        asyncio.run(llm.chat_litellm("m1", [], []))


def test_chat_dispatches_by_catalog_provider(monkeypatch):
    seen = []

    async def fake_litellm(model, messages, tools, on_delta=None):
        seen.append(model)
        return {"text": "ok", "tool_calls": []}

    async def fake_get():
        catalog._entries["litellm"] = (0.0, [{"id": "m-l", "provider": "litellm", "label": "m", "group": "g"}])
        return []

    monkeypatch.setattr(llm, "chat_litellm", fake_litellm)
    monkeypatch.setattr(catalog, "_entries", {})
    monkeypatch.setattr(catalog, "get", fake_get)
    assert asyncio.run(llm.chat("m-l", [], []))["text"] == "ok"
    with pytest.raises(llm.LlmError, match="unknown model"):
        asyncio.run(llm.chat("missing", [], []))
    assert seen == ["m-l"]


def test_assistant_message_roundtrip_shape():
    msg = llm.assistant_message({"text": "", "tool_calls": [{"id": "c1", "name": "t", "args": {"a": 1}}]})
    assert msg["content"] is None
    assert msg["tool_calls"][0]["function"] == {"name": "t", "arguments": '{"a": 1}'}


def test_gemini_conversion_pairs_tool_results_with_names():
    from app.agent.llm_gemini import to_contents, to_declarations

    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "go"},
        llm.assistant_message({"text": "", "tool_calls": [{"id": "c1", "name": "echo", "args": {"text": "hi"}}]}),
        {"role": "tool", "tool_call_id": "c1", "content": '{"ok": true}'},
    ]
    system, contents = to_contents(messages)
    assert system == "sys"
    assert [c.role for c in contents] == ["user", "model", "user"]
    parts = contents[2].parts or []
    fr = parts[0].function_response
    assert fr is not None and fr.name == "echo" and fr.id == "c1"
    tool = {"type": "function", "function": {"name": "echo", "description": "d", "parameters": {"type": "object"}}}
    decls = to_declarations([tool]) or []
    assert (decls[0].function_declarations or [])[0].name == "echo"


def test_chat_litellm_skips_a_malformed_sse_line(monkeypatch):
    monkeypatch.setenv("LITELLM_BASE_URL", "http://litellm.test/v1")
    monkeypatch.setenv("LITELLM_API_KEY", "k-test")

    def handler(request: httpx.Request) -> httpx.Response:
        good = b'data: {"choices": [{"delta": {"content": "ok"}}]}\n\n'
        return httpx.Response(200, content=b"data: {not json\n\n" + good + b"data: [DONE]\n\n")

    patch_client(monkeypatch, handler)
    result = asyncio.run(llm.chat_litellm("m1", [{"role": "user", "content": "x"}], [], None))
    assert result["text"] == "ok"
