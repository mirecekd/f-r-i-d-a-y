# backend/app/agent/llm.py
"""One chat interface over both providers: `chat(model, messages, tools, on_delta) -> {text, tool_calls}`.

Messages and tools use the OpenAI shapes. `tool_calls` is a list of {id, name, args: dict}; a Gemini call may
also carry `signature` (thought signature) which `assistant_message` keeps so the next round can echo it.
LiteLLM goes through its OpenAI-compatible /chat/completions (SSE stream); Gemini through google-genai.
A user message may carry a list of content parts instead of a string: `{type:'text', text}` and
`{type:'image_url', image_url:{url:'data:<mime>;base64,...'}}` (build with `image_part`); LiteLLM gets them as is,
Gemini turns them into text and inline_data parts.
"""

import base64
import json
import os
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.agent import thinking
from app.agent.catalog import catalog

OnDelta = Callable[[str], Awaitable[None]]
ChatResult = dict[str, Any]


class LlmError(RuntimeError):
    pass


async def chat(model: str, messages: list[dict], tools: list[dict], on_delta: OnDelta | None = None) -> ChatResult:
    provider = catalog.provider_of(model)
    if provider is None:
        await catalog.get()
        provider = catalog.provider_of(model)
    if provider == "gemini":
        from app.agent.llm_gemini import chat_gemini

        return await chat_gemini(model, messages, tools, on_delta)
    if provider == "litellm":
        return await chat_litellm(model, messages, tools, on_delta)
    raise LlmError(f"unknown model: {model}")


def assistant_message(result: ChatResult) -> dict[str, Any]:
    """The assistant turn to append to the history after `chat` returned `result`."""
    msg: dict[str, Any] = {"role": "assistant", "content": result["text"] or None}
    if result["tool_calls"]:
        msg["tool_calls"] = [
            {
                "id": c["id"],
                "type": "function",
                "function": {"name": c["name"], "arguments": json.dumps(c["args"])},
                **({"thought_signature": c["signature"]} if c.get("signature") else {}),
            }
            for c in result["tool_calls"]
        ]
    return msg


def image_part(data: bytes, mime: str) -> dict[str, Any]:
    """An OpenAI-style image content part holding `data` as a data URL."""
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode()}"}}


def split_data_url(url: str) -> tuple[str, bytes]:
    """`data:<mime>;base64,<payload>` -> (mime, bytes); LlmError for anything else."""
    head, sep, payload = url.partition(",")
    if not sep or not head.startswith("data:") or not head.endswith(";base64"):
        raise LlmError("image parts must be base64 data URLs")
    return head[5:-7], base64.b64decode(payload)


def parse_args(raw: str) -> dict[str, Any]:
    try:
        args = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}
    return args if isinstance(args, dict) else {}


def _litellm_messages(messages: list[dict]) -> list[dict]:
    """Drop Gemini-only keys that an OpenAI-compatible server may reject."""
    out = []
    for m in messages:
        if m.get("tool_calls"):
            m = {**m, "tool_calls": [{k: v for k, v in c.items() if k != "thought_signature"} for c in m["tool_calls"]]}
        out.append(m)
    return out


async def chat_litellm(
    model: str, messages: list[dict], tools: list[dict], on_delta: OnDelta | None = None
) -> ChatResult:
    base, key = os.getenv("LITELLM_BASE_URL"), os.getenv("LITELLM_API_KEY")
    if not base or not key:
        raise LlmError("LITELLM_BASE_URL / LITELLM_API_KEY not set")
    body: dict[str, Any] = {"model": model, "messages": _litellm_messages(messages), "stream": True}
    if tools:
        body["tools"] = tools
    if litellm_reasons(model):
        body["reasoning_effort"] = thinking.reasoning_effort()
    try:
        return await _post_litellm(base, key, body, on_delta)
    except _Rejected:
        thinking.LITELLM_REJECTED.add(model)
        body.pop("reasoning_effort")
        return await _post_litellm(base, key, body, on_delta)


def litellm_reasons(model: str) -> bool:
    """True when the catalog says `model` supports reasoning and the proxy has not rejected reasoning_effort."""
    return model not in thinking.LITELLM_REJECTED and catalog.has_cap(model, "reasoning")


class _Rejected(Exception):
    """The proxy answered 400 to a request carrying reasoning_effort."""


async def _post_litellm(base: str, key: str, body: dict[str, Any], on_delta: OnDelta | None) -> ChatResult:
    text: list[str] = []
    calls: dict[int, dict[str, str]] = {}
    url = base.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {key}"}
    async with (
        httpx.AsyncClient(timeout=httpx.Timeout(120, connect=15)) as client,
        client.stream("POST", url, json=body, headers=headers) as resp,
    ):
        if resp.status_code >= 400:
            detail = (await resp.aread()).decode(errors="replace")[:300]
            if resp.status_code == 400 and "reasoning_effort" in body:
                raise _Rejected(detail)
            raise LlmError(f"litellm {resp.status_code}: {detail}")
        async for line in resp.aiter_lines():
            if not line.startswith("data:") or line.strip() == "data: [DONE]":
                continue
            try:
                chunk = json.loads(line[5:])
            except ValueError:  # one malformed SSE line must not kill the whole turn
                continue
            for choice in chunk.get("choices", []):
                delta = choice.get("delta") or {}
                if delta.get("content"):
                    text.append(delta["content"])
                    if on_delta:
                        await on_delta(delta["content"])
                for tc in delta.get("tool_calls") or []:
                    slot = calls.setdefault(tc.get("index", 0), {"id": "", "name": "", "args": ""})
                    slot["id"] = tc.get("id") or slot["id"]
                    fn = tc.get("function") or {}
                    slot["name"] = fn.get("name") or slot["name"]
                    slot["args"] += fn.get("arguments") or ""
    tool_calls = [
        {"id": c["id"] or f"call_{i}", "name": c["name"], "args": parse_args(c["args"])}
        for i, c in sorted(calls.items())
        if c["name"]
    ]
    return {"text": "".join(text), "tool_calls": tool_calls}
