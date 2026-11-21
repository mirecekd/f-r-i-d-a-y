# backend/tests/test_live_text.py
"""Text turns over Gemini Live and the pinned-model plumbing for the voice session."""

import json

from google.genai import types

from app.agent import live_text, prefs
from app.voice import session as live_session
from app.voice.tools import Tool


async def noop_handler(args: dict) -> dict:
    return {}


def test_build_config_text_modality_and_blocking_tools():
    tool = Tool("t", "d", {"type": "object", "properties": {}}, handler=noop_handler, long=True)
    cfg = live_text.build_config("some-live", {"t": tool})
    assert cfg.response_modalities == [types.Modality.TEXT]
    declarations = [d for t in cfg.tools or [] if isinstance(t, types.Tool) for d in t.function_declarations or []]
    assert [d.behavior for d in declarations] == [types.Behavior.BLOCKING]


def test_build_config_audio_with_transcription_for_text_rejecting_models():
    live_text.AUDIO_ONLY.add("audio-live")
    try:
        cfg = live_text.build_config("audio-live", {})
    finally:
        live_text.AUDIO_ONLY.discard("audio-live")
    assert cfg.response_modalities == [types.Modality.AUDIO]
    assert cfg.output_audio_transcription is not None


def test_seed_turns_skips_system_last_user_and_tool_messages():
    history = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"},
        {"role": "tool", "content": "x"},
        {"role": "user", "content": "now"},
    ]
    turns = live_text.seed_turns(history)
    assert [(t.role, [p.text for p in t.parts or []]) for t in turns] == [("user", ["a"]), ("model", ["b"])]


def test_live_model_uses_pin_then_env_and_ignores_non_live_pin(monkeypatch):
    monkeypatch.setenv("GEMINI_LIVE_MODEL", "env-live")
    assert live_session.live_model() == "env-live"
    prefs.save_model("chat", "gemini-3.8-live-extended-thinking")
    assert live_session.live_model() == "gemini-3.8-live-extended-thinking"
    prefs.save_model("chat", "gemini-flash-latest")  # stale pin from before the role split
    assert live_session.live_model() == "env-live"
    assert json.loads(prefs.prefs_path().read_text())["chat_model"] == "gemini-flash-latest"
