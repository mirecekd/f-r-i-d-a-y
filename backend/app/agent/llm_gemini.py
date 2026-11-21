# backend/app/agent/llm_gemini.py
"""Gemini side of agent.llm: converts OpenAI-shaped messages/tools to google-genai and back."""

import base64
import os
import uuid
from typing import Any

from google import genai
from google.genai import errors, types

from app.agent import thinking
from app.agent.llm import ChatResult, LlmError, OnDelta, parse_args, split_data_url


def user_parts(content: Any) -> list[types.Part]:
    """A user message body (string or OpenAI-style content parts) as Gemini parts."""
    if not isinstance(content, list):
        return [types.Part(text=str(content))]
    parts: list[types.Part] = []
    for p in content:
        if p.get("type") == "image_url":
            mime, data = split_data_url(p["image_url"]["url"])
            parts.append(types.Part.from_bytes(data=data, mime_type=mime))
        else:
            parts.append(types.Part(text=str(p.get("text", ""))))
    return parts


def to_contents(messages: list[dict]) -> tuple[str | None, list[types.Content]]:
    system: list[str] = []
    contents: list[types.Content] = []
    names: dict[str, str] = {}  # tool_call_id -> function name, needed by function_response parts
    for m in messages:
        role = m["role"]
        if role == "system":
            system.append(str(m["content"]))
        elif role == "user":
            contents.append(types.Content(role="user", parts=user_parts(m["content"])))
        elif role == "assistant":
            parts: list[types.Part] = []
            if m.get("content"):
                parts.append(types.Part(text=m["content"]))
            for c in m.get("tool_calls") or []:
                fn = c["function"]
                names[c["id"]] = fn["name"]
                sig = c.get("thought_signature")
                parts.append(
                    types.Part(
                        function_call=types.FunctionCall(id=c["id"], name=fn["name"], args=parse_args(fn["arguments"])),
                        thought_signature=base64.b64decode(sig) if sig else None,
                    )
                )
            contents.append(types.Content(role="model", parts=parts))
        elif role == "tool":
            part = types.Part(
                function_response=types.FunctionResponse(
                    id=m["tool_call_id"], name=names.get(m["tool_call_id"], ""), response={"result": m["content"]}
                )
            )
            last = contents[-1] if contents else None
            if last and last.role == "user" and last.parts and last.parts[0].function_response:
                last.parts.append(part)  # parallel results travel in one user turn
            else:
                contents.append(types.Content(role="user", parts=[part]))
    return ("\n\n".join(system) or None), contents


def to_declarations(tools: list[dict]) -> list[types.Tool] | None:
    decls = [
        types.FunctionDeclaration(
            name=t["function"]["name"],
            description=t["function"].get("description", ""),
            parameters_json_schema=t["function"].get("parameters") or {"type": "object", "properties": {}},
        )
        for t in tools
    ]
    return [types.Tool(function_declarations=decls)] if decls else None


async def _open_stream(client: Any, model: str, contents: Any, system: str | None, declared: Any) -> Any:
    """Start the stream; when the model rejects the thinking config, learn that and retry (at most twice)."""
    for _ in range(2):
        config: Any = types.GenerateContentConfig(
            system_instruction=system, tools=declared, thinking_config=thinking.agent_config(model)
        )
        try:
            return await client.aio.models.generate_content_stream(model=model, contents=contents, config=config)
        except errors.APIError as e:
            if not thinking.AGENT.learn(model, str(e)):
                raise
    config = types.GenerateContentConfig(system_instruction=system, tools=declared, thinking_config=thinking.agent_config(model))
    return await client.aio.models.generate_content_stream(model=model, contents=contents, config=config)


async def chat_gemini(
    model: str, messages: list[dict], tools: list[dict], on_delta: OnDelta | None = None
) -> ChatResult:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise LlmError("GEMINI_API_KEY is not set")
    system, contents = to_contents(messages)
    declared: Any = to_declarations(tools)  # list[Tool] is invariant vs the SDK's ToolListUnion
    client = genai.Client(api_key=key)
    stream = await _open_stream(client, model, contents, system, declared)
    text: list[str] = []
    calls: list[dict[str, Any]] = []
    async for chunk in stream:
        for cand in chunk.candidates or []:
            for part in (cand.content.parts if cand.content and cand.content.parts else []):
                if part.function_call and part.function_call.name:
                    fc = part.function_call
                    call = {"id": fc.id or f"call_{uuid.uuid4().hex[:8]}", "name": fc.name, "args": dict(fc.args or {})}
                    if part.thought_signature:
                        call["signature"] = base64.b64encode(part.thought_signature).decode()
                    calls.append(call)
                elif part.text and not part.thought:
                    text.append(part.text)
                    if on_delta:
                        await on_delta(part.text)
    return {"text": "".join(text), "tool_calls": calls}
