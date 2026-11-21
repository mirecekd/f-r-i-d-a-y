# backend/app/agent/catalog_litellm.py
"""LiteLLM model list for the agent role, with capability flags from GET /model/info when the key may read it."""

from typing import Any

EXCLUDE = ("embed", "rerank", "stability", "nova-2-multimodal", "image")
REGIONS = ("eu", "us", "global", "apac")


def entry(model_id: str, caps: dict[str, bool] | None = None) -> dict[str, Any]:
    """`eu.anthropic.claude-opus-5` -> group 'anthropic', label 'claude-opus-5 (eu)'."""
    parts = model_id.split(".", 2)
    region = ""
    if len(parts) == 3 and parts[0] in REGIONS:
        region, group, name = parts
    elif len(parts) >= 2:
        group, name = parts[0], model_id.split(".", 1)[1]
    else:
        group, name = "litellm", model_id
    label = f"{name} ({region})" if region else name
    out: dict[str, Any] = {"id": model_id, "provider": "litellm", "label": label, "group": group, "roles": ["agent"]}
    if caps is not None:
        out["caps"] = caps
    return out


def filter_models(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Fallback from GET /models: no capability data, only the `mode` hint."""
    entries = []
    for item in payload.get("data", []):
        model_id = str(item.get("id", ""))
        mode = item.get("mode")
        if not model_id or any(x in model_id.lower() for x in EXCLUDE) or (mode and mode != "chat"):
            continue
        entries.append(entry(model_id))
    return sorted(entries, key=lambda e: (e["group"], e["label"]))


def filter_model_info(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """GET /model/info: chat models whose `supports_function_calling` is true (the agent loop needs tool calls)."""
    entries: dict[str, dict[str, Any]] = {}
    for item in payload.get("data", []):
        model_id = str(item.get("model_name", ""))
        info = item.get("model_info") or {}
        if not model_id or any(x in model_id.lower() for x in EXCLUDE) or info.get("mode") != "chat":
            continue
        if info.get("supports_function_calling") is not True:
            continue
        caps = {"tools": True, "vision": bool(info.get("supports_vision")), "reasoning": bool(info.get("supports_reasoning"))}
        entries[model_id] = entry(model_id, caps)
    return sorted(entries.values(), key=lambda e: (e["group"], e["label"]))
