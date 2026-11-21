# backend/app/voice/language.py
"""Selectable conversation languages. The pinned one lives in prefs (`language`); GEMINI_LANGUAGE is the fallback."""

import os

from app.agent import prefs

DEFAULT_LANGUAGE = "cs-CZ"

# code -> (label shown in the UI, English name used in the prompt)
LANGUAGES: dict[str, tuple[str, str]] = {
    "cs-CZ": ("Čeština", "Czech"),
    "en-US": ("English", "English"),
    "sk-SK": ("Slovenčina", "Slovak"),
    "de-DE": ("Deutsch", "German"),
    "pl-PL": ("Polski", "Polish"),
    "es-ES": ("Español", "Spanish"),
    "fr-FR": ("Français", "French"),
    "it-IT": ("Italiano", "Italian"),
    "uk-UA": ("Українська", "Ukrainian"),
}

# Live models that reject these language codes at connect (1007 "Unsupported language code"), found by probing.
# For them the code is left out of speech_config and the model picks the language from the prompt.
UNSUPPORTED_BY_MODEL: dict[str, frozenset[str]] = {
    "native-audio": frozenset({"cs-CZ", "sk-SK", "es-ES"}),
}


def language_list() -> list[dict[str, str]]:
    return [{"code": code, "label": label} for code, (label, _) in LANGUAGES.items()]


def current_language() -> str:
    """Pinned language, else GEMINI_LANGUAGE, else Czech; read at every session start."""
    for candidate in (prefs.language(), os.getenv("GEMINI_LANGUAGE")):
        if candidate in LANGUAGES:
            return candidate
    return DEFAULT_LANGUAGE


def english_name(code: str) -> str:
    return LANGUAGES[code][1]


def speech_language(model: str, code: str) -> str | None:
    """The code for speech_config.language_code, or None when `model` is known to reject it."""
    if any(part in model and code in codes for part, codes in UNSUPPORTED_BY_MODEL.items()):
        return None
    return code
