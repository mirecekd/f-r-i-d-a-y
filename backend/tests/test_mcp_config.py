# backend/tests/test_mcp_config.py
"""MCP schema sanitising and server config loading."""

import json

from app.mcp.config import load_specs
from app.mcp.schema import sanitize_schema


def test_sanitize_schema_for_gemini():
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#", "title": "T", "type": "object",
        "additionalProperties": False,
        "properties": {
            "a": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None, "title": "A"},
            "b": {"type": "array", "items": {"$ref": "#/$defs/Item"}},
            "c": {"type": ["string", "null"], "format": "uri"},
        },
        "required": ["b", "gone"],
        "$defs": {"Item": {"type": "object", "properties": {"k": {"type": "string", "default": "x"}}}},
    }
    out = sanitize_schema(schema)
    text = json.dumps(out)
    for banned in ("$schema", "additionalProperties", "default", "anyOf", "$ref", "$defs", "title", "uri"):
        assert banned not in text
    assert out["properties"]["a"] == {"type": "integer", "nullable": True}
    assert out["properties"]["b"]["items"]["properties"]["k"] == {"type": "string"}
    assert out["required"] == ["b"] and sanitize_schema(None) == {"type": "object", "properties": {}}


def test_config_url_env_disabled_until_set_and_secrets_by_name(tmp_path, monkeypatch):
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"mcpServers": {"ha": {"url_env": "T_HA_URL", "path": "/api/mcp", "token_env": "T_HA_TOK",
                                                       "allowed_tools": ["x"]}}}))
    monkeypatch.delenv("T_HA_URL", raising=False)
    (off,) = load_specs(path)
    assert not off.enabled and "T_HA_URL" in off.disabled_reason
    monkeypatch.setenv("T_HA_URL", "http://ha.test:8123/")
    (on,) = load_specs(path)
    assert on.url == "http://ha.test:8123/api/mcp"
    assert "T_HA_TOK" in vars(on).values() and "T_HA_TOK" in vars(off).values()


def test_shipped_config_is_valid_and_ha_is_off_by_default(monkeypatch):
    from app.mcp.config import SHIPPED

    monkeypatch.delenv("HA_URL", raising=False)
    monkeypatch.delenv("MCP_HUB_URL", raising=False)
    specs = {s.name: s for s in load_specs(SHIPPED)}
    assert specs["home-assistant"].enabled is False
    assert specs["home-assistant"].policies["homeassistant__GetLiveContext"]["risky"] is False
    assert specs["home-assistant"].policies["intent__HassTurnOn"]["risky"] is True
    assert "MCP_HUB_TOKEN" in vars(specs["hub"]).values()  # an env var NAME, never a value
