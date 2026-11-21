# backend/tests/test_vision_analyze.py
"""JSON repair, model choice, llm image parts and the analysis call (the model is mocked)."""

import asyncio
import json

import pytest

from app.agent import llm, llm_gemini
from app.agent.catalog import catalog
from app.vision import analyze, capability
from app.vision.parse import AnalysisParseError, parse_analysis
from tests.vision_helpers import png_bytes

GOOD = {"kind": "floorplan", "summary": "A flat.", "people_count": None, "objects": [{"label": "door", "count": 2}],
        "text_found": ["Kuchyn"], "rooms": [{"name": "Kuchyn", "dimensions": "4x5 m"}], "confidence": 0.8, "notes": ""}


def test_parse_accepts_fenced_json_with_prose():
    out = parse_analysis("Sure!\n```json\n" + json.dumps(GOOD) + "\n```\nDone")
    assert out["kind"] == "floorplan" and out["rooms"][0]["name"] == "Kuchyn" and out["confidence"] == 0.8


def test_parse_normalizes_bad_fields():
    out = parse_analysis(json.dumps({"kind": "weird", "summary": "s", "people_count": -3, "confidence": 7,
                                     "objects": ["cat", {"label": "dog", "count": 2}, 5], "text_found": "no", "rooms": ["Hall"]}))
    assert out["kind"] == "other" and out["people_count"] is None and out["confidence"] == 1.0
    assert out["objects"] == [{"label": "cat", "count": 1}, {"label": "dog", "count": 2}]
    assert out["text_found"] == [] and out["rooms"] == [{"name": "Hall", "dimensions": None}]


@pytest.mark.parametrize("text", ["no json here", "{broken", "[1, 2]", '{"kind": "photo"}'])
def test_parse_errors(text):
    with pytest.raises(AnalysisParseError):
        parse_analysis(text)


@pytest.fixture
def vision_everywhere(monkeypatch):
    async def pick(pinned):
        return pinned

    monkeypatch.setattr(analyze, "pick_vision_model", pick)


def test_analyze_retries_once_on_invalid_json(monkeypatch, vision_everywhere):
    calls = []

    async def fake_chat(model, messages, tools, on_delta=None):
        calls.append(messages)
        return {"text": "oops not json" if len(calls) == 1 else json.dumps(GOOD), "tool_calls": []}

    monkeypatch.setattr(llm, "chat", fake_chat)
    model, result = asyncio.run(analyze.analyze_picture(b"jpegbytes", {"lat": 1.0, "lon": 2.0}, "m1"))
    assert model == "m1" and result["kind"] == "floorplan" and len(calls) == 2
    first_user = calls[0][1]["content"]
    assert first_user[1]["type"] == "image_url" and first_user[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert calls[1][-1]["role"] == "user" and "not valid" in calls[1][-1]["content"]


def test_analyze_gives_up_after_second_failure(monkeypatch, vision_everywhere):
    async def fake_chat(model, messages, tools, on_delta=None):
        return {"text": "still nothing", "tool_calls": []}

    monkeypatch.setattr(llm, "chat", fake_chat)
    with pytest.raises(AnalysisParseError):
        asyncio.run(analyze.analyze_picture(b"x", {}, "m1"))


def test_pinned_model_used_when_vision_capable_else_fallback(monkeypatch):
    async def entries():
        return []

    async def vision_ids():
        return {"vis"}

    monkeypatch.setattr(catalog, "get", entries)
    monkeypatch.setattr(capability, "_litellm_vision_ids", vision_ids)
    monkeypatch.setattr(catalog, "provider_of", lambda m: {"vis": "litellm", "txt": "litellm", "g": "gemini"}.get(m))
    pick = lambda m: asyncio.run(capability.pick_vision_model(m))  # noqa: E731
    assert pick("vis") == "vis"
    assert pick("g") == "g"
    assert pick("txt") == capability.FALLBACK_MODEL
    assert pick("unknown") == capability.FALLBACK_MODEL


def test_image_part_round_trips_through_gemini_parts():
    data = png_bytes()
    messages = [{"role": "user", "content": [{"type": "text", "text": "look"}, llm.image_part(data, "image/png")]}]
    _, contents = llm_gemini.to_contents(messages)
    parts = contents[0].parts
    assert parts is not None and parts[0].text == "look"
    blob = parts[1].inline_data
    assert blob is not None and blob.mime_type == "image/png" and blob.data == data


def test_plain_string_user_message_is_unchanged_for_gemini():
    _, contents = llm_gemini.to_contents([{"role": "user", "content": "hi"}])
    parts = contents[0].parts
    assert parts is not None and parts[0].text == "hi"


def test_non_data_url_image_part_is_refused():
    with pytest.raises(llm.LlmError):
        llm.split_data_url("https://example.com/a.png")
