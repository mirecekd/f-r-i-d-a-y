# backend/app/agent/catalog_gemini.py
"""Gemini API model lists: Live (bidiGenerateContent) models for the chat role, text models for the agent role."""

from typing import Any

LIVE_EXCLUDE = ("transcribe", "translate", "genie", "robotics")
TEXT_EXCLUDE = (
    "tts", "image", "imagen", "veo", "banana", "nano", "transcribe", "lyria", "robotics", "computer-use",
    "antigravity", "deep-research", "omni", "live", "audio", "embedding", "aqa", "learnlm", "gemma",
)  # fmt: skip
LEGACY_LIVE = "gemini-3.1-flash-live"


def model_id(m: Any) -> str:
    return str(m.name or "").removeprefix("models/")


def live_label(mid: str, display_name: str | None) -> str:
    label = display_name or mid
    if "extended-thinking" in mid:
        label += " (async only, no scheduling)"
    elif LEGACY_LIVE in mid:
        label += " (legacy: no async tools)"
    return label


def filter_live(models: list[Any]) -> list[dict[str, Any]]:
    entries = []
    for m in models:
        mid = model_id(m)
        if "bidiGenerateContent" not in (m.supported_actions or []) or not mid:
            continue
        if any(x in mid.lower() for x in LIVE_EXCLUDE):
            continue
        entries.append(
            {"id": mid, "provider": "gemini", "label": live_label(mid, m.display_name), "group": "google live", "roles": ["chat"]}
        )
    return sorted(entries, key=lambda e: e["id"], reverse=True)


def filter_text(models: list[Any]) -> list[dict[str, Any]]:
    entries = []
    for m in models:
        mid = model_id(m)
        if "generateContent" not in (m.supported_actions or []) or not mid.startswith("gemini"):
            continue
        if any(x in mid.lower() for x in TEXT_EXCLUDE):
            continue
        caps = {"tools": True, "vision": True, "reasoning": bool(getattr(m, "thinking", False))}
        entries.append(
            {"id": mid, "provider": "gemini", "label": m.display_name or mid, "group": "google", "roles": ["agent"], "caps": caps}
        )
    return sorted(entries, key=lambda e: e["label"])
