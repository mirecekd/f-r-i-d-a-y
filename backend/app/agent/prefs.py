# backend/app/agent/prefs.py
"""Pinned preferences, persisted as JSON under FRIDAY_DATA_DIR (default /srv/data).

Keys: agent_model, chat_model (model ids), language (BCP-47 code), voice ({model id: prebuilt voice id}).
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger("friday.agent.prefs")

ROLES = {"agent": "agent_model", "chat": "chat_model"}


def prefs_path() -> Path:
    return Path(os.getenv("FRIDAY_DATA_DIR", "/srv/data")) / "prefs.json"


def _read() -> dict[str, Any]:
    path = prefs_path()
    if not path.exists():
        return {}
    try:
        stored = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        log.warning("prefs unreadable: %s", type(e).__name__)
        return {}
    return stored if isinstance(stored, dict) else {}


def _write(current: dict[str, Any]) -> None:
    path = prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(current, indent=2))
    tmp.replace(path)


def load() -> dict[str, str | None]:
    stored = _read()
    return {key: stored.get(key) if isinstance(stored.get(key), str) else None for key in ROLES.values()}


def save_model(role: str, model: str) -> None:
    """Pin `model` for `role` ('agent' | 'chat'); other keys already in the file are kept."""
    current = _read()
    current[ROLES[role]] = model
    _write(current)


def language() -> str | None:
    """The pinned conversation language code, or None."""
    value = _read().get("language")
    return value if isinstance(value, str) else None


def save_language(code: str) -> None:
    current = _read()
    current["language"] = code
    _write(current)


def voice_for(model: str) -> str | None:
    """The voice pinned for `model`, or None."""
    voices = _read().get("voice")
    value = voices.get(model) if isinstance(voices, dict) else None
    return value if isinstance(value, str) else None


def save_voice(model: str, voice: str) -> None:
    current = _read()
    voices = current.get("voice")
    current["voice"] = {**(voices if isinstance(voices, dict) else {}), model: voice}
    _write(current)
