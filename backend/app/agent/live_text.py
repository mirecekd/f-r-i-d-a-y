# backend/app/agent/live_text.py
"""Text-only turn through a Gemini Live model: one short Live connection per chat turn, tools via the same registry."""

import logging
import os
from dataclasses import replace
from typing import Any

from google import genai
from google.genai import errors, types

from app.agent.llm import OnDelta
from app.agent.loop import MAX_ROUNDS, Emit, run_tool
from app.agent.prompt import CHAT_PROMPT
from app.voice.session import LANGUAGE
from app.voice.tools import Tool, ToolRegistry

log = logging.getLogger("friday.agent.live_text")

AUDIO_ONLY: set[str] = set()  # models that rejected response_modalities=['TEXT']; they answer in audio + transcription


def seed_turns(history: list[dict[str, Any]]) -> list[types.Content]:
    """Earlier plain-text user/assistant messages as Live turns; the last user message is sent separately."""
    turns = []
    for m in history[1:-1]:
        if m["role"] in ("user", "assistant") and isinstance(m.get("content"), str) and m["content"]:
            turns.append(types.Content(role="user" if m["role"] == "user" else "model", parts=[types.Part(text=m["content"])]))
    return turns


def build_config(model: str, tools: dict[str, Tool]) -> types.LiveConnectConfig:
    audio = model in AUDIO_ONLY
    plain = {n: replace(t, long=False) for n, t in tools.items()}  # no NON_BLOCKING semantics in text
    return types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO if audio else types.Modality.TEXT],
        system_instruction=CHAT_PROMPT,
        tools=ToolRegistry(plain).tool_config(),  # pyright: ignore[reportArgumentType]
        output_audio_transcription=types.AudioTranscriptionConfig() if audio else None,
        speech_config=types.SpeechConfig(language_code=LANGUAGE) if audio else None,
    )


async def run_turn(model: str, history: list[dict[str, Any]], tools: dict[str, Tool], emit: Emit, on_delta: OnDelta) -> str:
    """Answer the last user message in `history`, stream text through `on_delta`, append the reply to `history`."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    client = genai.Client(api_key=key)
    try:
        text = await _turn(client, model, history, tools, emit, on_delta)
    except errors.APIError as e:
        if model in AUDIO_ONLY or "modalit" not in str(e).lower():
            raise
        log.info("%s does not support TEXT responses; using audio with transcription", model)
        AUDIO_ONLY.add(model)
        text = await _turn(client, model, history, tools, emit, on_delta)
    history.append({"role": "assistant", "content": text})
    return text


async def _turn(client: Any, model: str, history: list[dict[str, Any]], tools: dict[str, Tool], emit: Emit, on_delta: OnDelta) -> str:
    audio = model in AUDIO_ONLY
    out = ""
    async with client.aio.live.connect(model=model, config=build_config(model, tools)) as session:
        turns = seed_turns(history)
        if turns:
            await session.send_client_content(turns=turns, turn_complete=False)
        await session.send_client_content(
            turns=types.Content(role="user", parts=[types.Part(text=history[-1]["content"])]), turn_complete=True
        )
        for _ in range(MAX_ROUNDS):
            calls: list[types.FunctionCall] = []
            async for msg in session.receive():
                sc = msg.server_content
                if sc and audio and sc.output_transcription and sc.output_transcription.text:
                    out += sc.output_transcription.text
                    await on_delta(sc.output_transcription.text)
                elif sc and not audio and sc.model_turn:
                    for part in sc.model_turn.parts or []:
                        if part.text and not part.thought:
                            out += part.text
                            await on_delta(part.text)
                if msg.tool_call:
                    calls.extend(msg.tool_call.function_calls or [])
                    break  # the turn stays open until the tool responses are sent
            if not calls:
                break
            responses = []
            for call in calls:
                result = await run_tool(tools, {"id": call.id or "", "name": call.name or "", "args": dict(call.args or {})}, emit)
                responses.append(types.FunctionResponse(id=call.id, name=call.name, response={"result": result}))
            await session.send_tool_response(function_responses=responses)
    return out
