# backend/app/agent/thinking_litellm.py
"""reasoning_effort for LiteLLM models, with a per-model table that is learned from the proxy's 400 answers.

`max` means the strongest effort the model takes: the catalog (`/model/info`) names it per model (`max_effort`),
a 400 that lists the allowed values replaces it (`learn`); one that lists nothing steps max -> xhigh -> high.
Probed on the real proxy: Claude, GPT, Kimi, Qwen and Grok ids accept low..xhigh and max; DeepSeek rejects
xhigh/max without listing values. No separate Anthropic `thinking` budget is sent: every Claude id that
reports adaptive thinking also reports `max` effort, which is the stronger and cheaper way to ask.
"""

import re
from typing import Any

EFFORTS = ("minimal", "low", "medium", "high", "xhigh", "max")
BASE_EFFORT = {"minimal": "low", "low": "low", "medium": "medium", "high": "high"}
_ALLOWED_LIST = re.compile(r"(?:one of|supported values are|allowed values?(?: are)?)\s*:?\s*(.+)", re.I | re.S)

REJECTED: set[str] = set()  # models whose proxy refuses reasoning_effort altogether
CEILING: dict[str, str] = {}  # model -> highest effort the proxy accepted or listed for it


def top_effort(info: dict[str, Any]) -> str | None:
    """Highest effort above `high` that `/model/info` advertises for a model, else None."""
    levels = [x for x in info.get("reasoning_effort_levels") or [] if x in EFFORTS]
    top = max(levels, key=EFFORTS.index) if levels else None
    if top is None:
        top = "max" if info.get("supports_max_reasoning_effort") else "xhigh" if info.get("supports_xhigh_reasoning_effort") else None
    return top if top in ("xhigh", "max") else None


def effort(model: str, level: str, catalog_top: str | None) -> str:
    """The reasoning_effort value to send for unified `level`; `max` becomes the model's strongest effort."""
    if level != "max":
        return BASE_EFFORT[level]
    return CEILING.get(model) or catalog_top or "high"


def allowed_values(error: str) -> set[str]:
    """Effort names listed after 'must be one of' / 'supported values are' in a 400 text."""
    m = _ALLOWED_LIST.search(error)
    return {x for x in re.findall(r"[a-z]+", m.group(1).lower()) if x in EFFORTS} if m else set()


def learn(model: str, sent: str, error: str) -> None:
    """Remember what a 400 says about `sent`: a lower ceiling for xhigh/max, else no reasoning_effort at all."""
    allowed = allowed_values(error)
    if sent in ("xhigh", "max") and allowed and sent not in allowed:
        CEILING[model] = max(allowed, key=EFFORTS.index)
    elif sent == "max" and not allowed:
        CEILING[model] = "xhigh"
    elif sent == "xhigh" and not allowed:
        CEILING[model] = "high"
    else:
        REJECTED.add(model)
