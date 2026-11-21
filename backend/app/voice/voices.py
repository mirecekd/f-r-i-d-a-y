# backend/app/voice/voices.py
"""Prebuilt Live voices: id, UI label, gender hint and the one-word character from the Gemini speech docs.

Gender follows the API voice catalog where it lists the voice and the documented voice samples otherwise.
Probed with a real Live turn (Czech or English prompt, audio out): all 30 voices connect on gemini-3.8-live
(cs-CZ) and on gemini-2.5-flash-native-audio-latest (en-US), so the per-model override table is empty.
"""

import os

from app.agent import prefs

# Female by default: Kore is documented as "firm" (clear, brisk delivery) which suits a terse, factual assistant.
DEFAULT_VOICE = "Kore"

# (id, gender, style); the UI label is the id
_TABLE: list[tuple[str, str, str]] = [
    ("Zephyr", "female", "bright"), ("Puck", "male", "upbeat"), ("Charon", "male", "informative"),
    ("Kore", "female", "firm"), ("Fenrir", "male", "excitable"), ("Leda", "female", "youthful"),
    ("Orus", "male", "firm"), ("Aoede", "female", "breezy"), ("Callirrhoe", "female", "easy-going"),
    ("Autonoe", "female", "bright"), ("Enceladus", "male", "breathy"), ("Iapetus", "male", "clear"),
    ("Umbriel", "male", "easy-going"), ("Algieba", "male", "smooth"), ("Despina", "female", "smooth"),
    ("Erinome", "female", "clear"), ("Algenib", "male", "gravelly"), ("Rasalgethi", "male", "informative"),
    ("Laomedeia", "female", "upbeat"), ("Achernar", "female", "soft"), ("Alnilam", "male", "firm"),
    ("Schedar", "male", "even"), ("Gacrux", "female", "mature"), ("Pulcherrima", "female", "forward"),
    ("Achird", "male", "friendly"), ("Zubenelgenubi", "male", "casual"), ("Vindemiatrix", "female", "gentle"),
    ("Sadachbia", "male", "lively"), ("Sadaltager", "male", "knowledgeable"), ("Sulafat", "female", "warm"),
]  # fmt: skip

VOICES: list[dict[str, str]] = [{"id": v, "label": v, "gender": g, "style": s} for v, g, s in _TABLE]

# model id -> voice ids it accepts, only for models known to support fewer than all of VOICES
MODEL_VOICES: dict[str, list[str]] = {}


def voices_for(model: str) -> list[dict[str, str]]:
    allowed = MODEL_VOICES.get(model)
    return [v for v in VOICES if allowed is None or v["id"] in allowed]


def is_valid(model: str, voice: str) -> bool:
    return any(v["id"] == voice for v in voices_for(model))


def current_voice(model: str) -> str:
    """The voice pinned for `model` if still valid, else GEMINI_VOICE if valid, else the default (or the first allowed)."""
    for candidate in (prefs.voice_for(model), os.getenv("GEMINI_VOICE"), DEFAULT_VOICE):
        if candidate is not None and is_valid(model, candidate):
            return candidate
    return voices_for(model)[0]["id"]
