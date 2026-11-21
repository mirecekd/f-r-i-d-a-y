# backend/app/mcp/schema.py
"""MCP inputSchema -> the JSON-Schema subset Gemini Live accepts for function declarations."""

from typing import Any

KEEP = {"type", "description", "properties", "required", "items", "enum", "nullable",
        "minimum", "maximum", "minItems", "maxItems", "format"}
FORMATS = {"enum", "date-time"}  # Gemini rejects other `format` values


def _non_null(options: list[Any]) -> list[Any]:
    return [o for o in options if not (isinstance(o, dict) and o.get("type") == "null")]


def _resolve(node: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.rsplit("/", 1)[-1] in defs:
        return {**defs[ref.rsplit("/", 1)[-1]], **{k: v for k, v in node.items() if k != "$ref"}}
    return node


def _clean(node: Any, defs: dict[str, Any], depth: int) -> Any:
    if not isinstance(node, dict) or depth > 8:
        return {"type": "string"} if depth > 8 else node
    node = _resolve(node, defs)
    for key in ("anyOf", "oneOf"):  # Optional[X] is anyOf [X, null]; other unions keep their first branch
        options = node.get(key)
        if isinstance(options, list) and options:
            real = _non_null(options)
            node = {**{k: v for k, v in node.items() if k != key}, **_resolve(real[0] if real else {"type": "string"}, defs)}
            node["nullable"] = len(real) != len(options) or None
    kind = node.get("type")
    if isinstance(kind, list):
        real_types = [t for t in kind if t != "null"]
        node = {**node, "type": real_types[0] if real_types else "string", "nullable": len(real_types) != len(kind) or None}
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key not in KEEP or value is None or (key == "format" and value not in FORMATS):
            continue
        if key == "properties" and isinstance(value, dict):
            out[key] = {name: _clean(sub, defs, depth + 1) for name, sub in value.items()}
        elif key == "items":
            out[key] = _clean(value, defs, depth + 1)
        elif key == "type":
            out[key] = str(value).lower() if isinstance(value, str) else "string"
        else:
            out[key] = value
    if out.get("type") == "object" or "properties" in out:
        out["type"] = "object"
        props = out.setdefault("properties", {})
        if "required" in out:
            out["required"] = [r for r in out["required"] if r in props]
            if not out["required"]:
                del out["required"]
    if out.get("type") == "array" and "items" not in out:
        out["items"] = {"type": "string"}
    return out


def sanitize_schema(schema: dict[str, Any] | None) -> dict[str, Any]:
    """Always returns an object schema; unsupported keywords ($schema, additionalProperties, default,
    title, $defs, anyOf, ...) are dropped or collapsed."""
    schema = schema or {}
    defs = {**schema.get("definitions", {}), **schema.get("$defs", {})}
    out = _clean(schema, defs, 0)
    out["type"] = "object"
    out.setdefault("properties", {})
    return out
