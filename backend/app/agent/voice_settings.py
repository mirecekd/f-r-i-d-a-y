# backend/app/agent/voice_settings.py
"""Language, voice and thinking pinning: validation of `set_language` / `set_voice` / `set_thinking` and the extra fields of the `models` message."""

from typing import Any

from app.agent import prefs, thinking
from app.voice.language import LANGUAGES, current_language, language_list
from app.voice.voices import current_voice, is_valid, voices_for

NEXT_SESSION_NOTICE = "Změna se projeví v dalším hlasovém sezení"


def models_fields(chat_model: str) -> dict[str, Any]:
    """language, languages, voice and voices (of the pinned chat model) for the `models` message."""
    return {
        "language": current_language(),
        "languages": language_list(),
        "voice": current_voice(chat_model),
        "voices": voices_for(chat_model),
        "thinking": thinking.current(),
        "thinking_levels": list(thinking.LEVELS),
    }


def apply_language(msg: dict) -> str | None:
    """Pin the language; returns an error text for an unknown code."""
    code = msg.get("language")
    if not isinstance(code, str) or code not in LANGUAGES:
        return f"set_language: unknown language {code}"
    prefs.save_language(code)
    return None


def apply_voice(chat_model: str, msg: dict) -> str | None:
    """Pin the voice for the current chat model; returns an error text for a voice the model does not offer."""
    voice = msg.get("voice")
    if not isinstance(voice, str) or not is_valid(chat_model, voice):
        return f"set_voice: voice {voice} is not available for model {chat_model}"
    prefs.save_voice(chat_model, voice)
    return None


def apply_thinking(msg: dict) -> str | None:
    """Pin the thinking level; returns an error text for an unknown level."""
    level = msg.get("level")
    if not isinstance(level, str) or level not in thinking.LEVELS:
        return f"set_thinking: unknown level {level}"
    prefs.save_thinking(level)
    return None
