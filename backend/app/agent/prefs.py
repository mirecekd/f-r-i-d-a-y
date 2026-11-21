# backend/app/agent/prefs.py
"""Pinned models, persisted as JSON ({agent_model, chat_model}) under FRIDAY_DATA_DIR (default /srv/data)."""

import json
import logging
import os
from pathlib import Path

log = logging.getLogger("friday.agent.prefs")

ROLES = {"agent": "agent_model", "chat": "chat_model"}


def prefs_path() -> Path:
    return Path(os.getenv("FRIDAY_DATA_DIR", "/srv/data")) / "prefs.json"


def load() -> dict[str, str | None]:
    stored: dict = {}
    path = prefs_path()
    if path.exists():
        try:
            stored = json.loads(path.read_text())
        except (OSError, ValueError) as e:
            log.warning("prefs unreadable: %s", type(e).__name__)
    return {key: stored.get(key) if isinstance(stored.get(key), str) else None for key in ROLES.values()}


def save_model(role: str, model: str) -> None:
    """Pin `model` for `role` ('agent' | 'chat'); other keys already in the file are kept."""
    path = prefs_path()
    try:
        current = json.loads(path.read_text())
    except (OSError, ValueError):
        current = {}
    current[ROLES[role]] = model
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(current, indent=2))
    tmp.replace(path)
