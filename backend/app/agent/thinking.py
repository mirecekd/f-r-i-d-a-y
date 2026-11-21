# backend/app/agent/thinking.py
"""Unified thinking level (minimal|low|medium|high, default high) for the Live voice model, Live text turns,
Gemini agent models (generateContent) and LiteLLM models (reasoning_effort).

Models differ in what they accept; the tables below were found by probing the real API and are extended at
runtime when a model rejects the config (see `Rejections.learn`)."""

import os
import re

from google.genai import types

from app.agent import prefs

LEVELS = ("minimal", "low", "medium", "high")
DEFAULT_LEVEL = "high"
GEMINI_BUDGET = {"high": -1, "medium": 8192, "low": 1024}  # thinking_budget for models without thinking levels
LITELLM_EFFORT = {"minimal": "low", "low": "low", "medium": "medium", "high": "high"}
_LEVEL_REJECTED = re.compile(r"thinking level (minimal|low|medium|high) is not supported", re.I)


def current() -> str:
    """Pinned level, else FRIDAY_THINKING, else high; read at every request."""
    for candidate in (prefs.thinking(), (os.getenv("FRIDAY_THINKING") or "").lower()):
        if candidate in LEVELS:
            return candidate
    return DEFAULT_LEVEL


def _enum(level: str) -> types.ThinkingLevel:
    return types.ThinkingLevel(level.upper())


class Rejections:
    """What one API path learned about models: no thinking config at all, rejected levels, budget-only."""

    def __init__(self, unsupported: str, no_config: set[str], bad_levels: dict[str, set[str]]):
        self.unsupported = unsupported  # 'omit' | 'budget': what "Thinking level is not supported" means here
        self.no_config = no_config
        self.bad_levels = bad_levels
        self.budget_only: set[str] = set()

    def usable_level(self, model: str, level: str) -> str | None:
        """`level`, or the next higher one the model accepts; None when it accepts none."""
        bad = self.bad_levels.get(model, set())
        return next((x for x in LEVELS[LEVELS.index(level) :] if x not in bad), None)

    def learn(self, model: str, error: str) -> bool:
        """Remember what `error` says about `model`; True when the next attempt will differ."""
        text = error.lower()
        if "must be specified" in text and model in self.no_config:
            self.no_config.discard(model)  # a config table entry that went stale: the model now requires one
        elif (m := _LEVEL_REJECTED.search(error)) and m.group(1).lower() not in self.bad_levels.get(model, set()):
            self.bad_levels.setdefault(model, set()).add(m.group(1).lower())
        elif "thinking level is not supported" in text and self.unsupported == "budget" and model not in self.budget_only:
            self.budget_only.add(model)
        elif "thinking" in text and model not in self.no_config:
            self.no_config.add(model)
        else:
            return False
        return True


# Live: gemini-3.8-live rejects any thinking config (1007); the extended-thinking model requires one, not MINIMAL.
LIVE = Rejections("omit", {"gemini-3.8-live"}, {"gemini-3.8-live-extended-thinking": {"minimal"}})
# generateContent (agent and Live-text fallback): gemini-3.1-pro / 3.8-flash / flash-latest reject MINIMAL.
AGENT = Rejections("budget", set(), {"gemini-3.1-pro-preview": {"minimal"}, "gemini-flash-latest": {"minimal"}})
LITELLM_REJECTED: set[str] = set()  # models whose proxy answered 400 to reasoning_effort


def live_config(model: str, level: str | None = None) -> types.ThinkingConfig | None:
    """thinking_config for a Live connection, or None when `model` is known to reject it."""
    usable = LIVE.usable_level(model, level or current())
    if model in LIVE.no_config or usable is None:
        return None
    return types.ThinkingConfig(thinking_level=_enum(usable), include_thoughts=False)


def _budget(model: str, level: str) -> int:
    if level == "minimal":
        return 0 if "2.5-flash" in model and "lite" not in model else 128
    return GEMINI_BUDGET[level]


def agent_config(model: str, level: str | None = None) -> types.ThinkingConfig | None:
    """thinking_config for generateContent: levels for 3.x models, thinking_budget for 2.5 (and learned) ones."""
    wanted = level or current()
    if model in AGENT.no_config:
        return None
    usable = AGENT.usable_level(model, wanted)
    if model.startswith("gemini-2.5") or model in AGENT.budget_only or usable is None:
        return types.ThinkingConfig(thinking_budget=_budget(model, wanted), include_thoughts=False)
    return types.ThinkingConfig(thinking_level=_enum(usable), include_thoughts=False)


def reasoning_effort(level: str | None = None) -> str:
    return LITELLM_EFFORT[level or current()]
