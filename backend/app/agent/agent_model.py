# backend/app/agent/agent_model.py
"""The agent model that is used: the pinned one, else the newest Gemini flash in the live catalog.

A pin whose model vanished from the (loaded) catalog falls back to that default; the caller tells the user."""

import os

from app.agent import catalog_gemini as gemini
from app.agent import prefs
from app.agent.catalog import catalog

DEFAULT_MODEL = "gemini-3.8-flash"  # used until the catalog has been fetched, and when it has no 3.x flash


def default_model() -> str:
    """Newest stable `gemini-3*-flash` in the catalog (a preview when none is stable), else DEFAULT_MODEL."""
    ids = [e["id"] for e in catalog.entries_for("gemini") if "agent" in e["roles"]]
    return gemini.newest_flash(ids) or DEFAULT_MODEL


def pin() -> str | None:
    return prefs.load()["agent_model"] or os.getenv("FRIDAY_AGENT_MODEL") or None


def resolve() -> tuple[str, str | None]:
    """(model to use, stale pin or None): the pin falls back to the default when its provider's catalog lacks it."""
    pinned = pin()
    if not pinned:
        return default_model(), None
    entries = catalog.entries_for("gemini" if pinned.startswith("gemini") else "litellm")
    if entries and not any(e["id"] == pinned and "agent" in e["roles"] for e in entries):
        return default_model(), pinned
    return pinned, None
