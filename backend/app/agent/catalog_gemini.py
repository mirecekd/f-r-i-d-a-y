# backend/app/agent/catalog_gemini.py
"""Gemini API model lists: Live (bidiGenerateContent) models for the chat role, text models for the agent role."""

import re
from typing import Any

MIN_GEMINI_GENERATION = 3  # agent models older than this behave differently (thinking, tool calls) and are not offered
HIGH_ONLY = ("gemini-4-neon",)  # probed: accepts thinking level HIGH only
_GENERATION = re.compile(r"^gemini-(\d+)(?:\.(\d+))?-")
_FLASH = re.compile(r"^gemini-(\d+)(?:\.(\d+))?-flash(-preview)?$")

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


def generation(mid: str) -> int | None:
    """Major generation of `gemini-3.5-flash` -> 3; None for ids without one (the `-latest` aliases)."""
    m = _GENERATION.match(mid)
    return int(m.group(1)) if m else None


def newest_flash(ids: list[str]) -> str | None:
    """Newest `gemini-<major>[.<minor>]-flash` by version, stable ids before previews; None when there is none."""
    found = []
    for mid in ids:
        m = _FLASH.match(mid)
        if m and int(m.group(1)) >= MIN_GEMINI_GENERATION:
            found.append((m.group(3) is None, int(m.group(1)), int(m.group(2) or 0), mid))
    return max(found)[3] if found else None


def text_label(mid: str, display_name: str | None) -> str:
    label = display_name or mid
    return label + " (high thinking only)" if mid in HIGH_ONLY else label


def filter_text(models: list[Any]) -> list[dict[str, Any]]:
    entries = []
    for m in models:
        mid = model_id(m)
        if "generateContent" not in (m.supported_actions or []) or not mid.startswith("gemini"):
            continue
        if any(x in mid.lower() for x in TEXT_EXCLUDE) or (generation(mid) or 0) < MIN_GEMINI_GENERATION:
            continue
        caps = {"tools": True, "vision": True, "reasoning": bool(getattr(m, "thinking", False))}
        entries.append(
            {"id": mid, "provider": "gemini", "label": text_label(mid, m.display_name), "group": "google", "roles": ["agent"], "caps": caps}
        )
    return sorted(entries, key=lambda e: e["label"])
