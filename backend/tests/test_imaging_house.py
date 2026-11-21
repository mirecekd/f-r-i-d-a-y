# backend/tests/test_imaging_house.py
"""house analysis parsing and repair, spec merge (conflicts, missing scale, openings), house tools and refine (Gemini faked)."""

import asyncio
import json

import pytest

from app.imaging import house, house_parse
from app.imaging.spec_merge import merge_to_spec
from app.model3d.packs.building import building_from_spec
from app.model3d.packs.building.spec import BuildingSpecError, normalize
from app.vision.parse import AnalysisParseError
from tests.imaging_helpers import analysis, room

RAW = {"summary": "House", "storeys": [{"name": "Ground", "level": 0, "height_m": 2.6, "rooms": [
    {"name": "Living", "width_m": 5.2, "depth_m": 5.0, "dimension_source": "label", "dimension_confidence": 0.9,
     "doors": [{"wall": "e", "offset_m": 1.0, "width_m": 0.9}], "windows": [{"wall": "n"}], "floor_color": "oak"},
    {"name": "Kitchen", "width_m": 4.0, "depth_m": 5.0, "relative_to": "Living", "side": "e"}]}],
    "exterior": {"roof_type": "gable", "roof_color": "red", "floors": 1, "wall_color": "beige", "window_grid": {"cols": 2, "rows": 1}},
    "conflicts": ["x"], "open_questions": ["Where is the door?"], "confidence": {"overall": 0.7}}


def run(coro):
    return asyncio.run(coro)


def test_parse_house_tolerates_fences_and_fixes_types():
    got = house_parse.parse_house("```json\n" + json.dumps(RAW) + "\n```")
    kitchen = got["storeys"][0]["rooms"][1]
    assert kitchen["relative_to"] == "Living" and kitchen["side"] == "e" and kitchen["width_m"] == 4.0
    assert got["exterior"]["window_grid"] == {"cols": 2, "rows": 1} and got["confidence"]["overall"] == 0.7
    bad = {**RAW, "storeys": [{"name": "G", "rooms": [{"name": "A", "width_m": "wide", "depth_m": -3}]}]}
    assert house_parse.parse_house(json.dumps(bad))["storeys"][0]["rooms"][0]["width_m"] is None


def test_parse_house_rejects_a_reply_without_rooms():
    with pytest.raises(AnalysisParseError):
        house_parse.parse_house('{"summary": "nothing", "storeys": []}')
    with pytest.raises(AnalysisParseError):
        house_parse.parse_house("no json here")


def test_ask_json_repairs_once_then_gives_up(monkeypatch):
    replies = iter(["not json", json.dumps(RAW)])
    seen = []

    async def fake_chat(model, messages, tools):
        seen.append(len(messages))
        return {"text": next(replies), "tool_calls": []}

    monkeypatch.setattr(house, "chat_gemini", fake_chat)
    got = run(house.ask_json("sys", [{"type": "text", "text": "t"}], "m", house_parse.parse_house))
    assert got["storeys"] and seen == [2, 4]  # the retry carries the bad reply and the reason

    async def always_bad(model, messages, tools):
        return {"text": "still bad", "tool_calls": []}

    monkeypatch.setattr(house, "chat_gemini", always_bad)
    with pytest.raises(AnalysisParseError):
        run(house.ask_json("sys", [], "m", house_parse.parse_house))


def test_sources_are_validated_and_the_model_is_gemini_only(monkeypatch):
    with pytest.raises(house.SourceError, match="at least one"):
        house.collect_sources([], [])
    with pytest.raises(house.SourceError, match="unknown image id"):
        house.collect_sources([], ["0" * 32])
    with pytest.raises(house.SourceError, match="at most"):
        house.collect_sources([], ["x"] * 9)
    from app.agent.catalog import catalog

    monkeypatch.setattr(catalog, "provider_of", lambda m: "litellm" if m == "gpt" else "gemini")
    assert run(house.pick_model("gpt")) == "gemini-flash-latest" and run(house.pick_model("gemini-3-flash")) == "gemini-3-flash"


def test_spec_merge_builds_a_valid_building_spec():
    spec, notes = merge_to_spec(house_parse.parse_house(json.dumps(RAW)))
    parts = building_from_spec(spec)
    rooms = {r["id"]: r["rect"] for r in spec["storeys"][0]["rooms"]}
    assert rooms["living"] == [0, 0, 5.2, 5.0] and rooms["kitchen"] == [5.2, 0.0, 4.0, 5.0]
    assert spec["roof"]["type"] == "gable" and spec["roof"]["color"] == "#b5442e" and spec["wall_color"] == "#d8c8a8"
    assert {o["kind"] for o in spec["storeys"][0]["openings"]} == {"door", "window"} and parts
    assert notes["conflicts"] == ["x"] and "Where is the door?" in notes["questions"]


def test_conflicting_dimensions_use_the_most_confident_and_report_it():
    r = room("Living", width_m=None, depth_m=None, candidates=[
        {"width_m": 5.0, "depth_m": 4.0, "source": "plan label", "confidence": 0.9},
        {"width_m": 6.5, "depth_m": 4.0, "source": "photo estimate", "confidence": 0.4}])
    spec, notes = merge_to_spec(analysis([r]))
    assert spec["storeys"][0]["rooms"][0]["rect"][2:] == [5.0, 4.0]
    assert any("plan label" in c and "photo estimate" in c for c in notes["conflicts"])


def test_missing_scale_asks_and_uses_the_default_or_the_footprint():
    unknown = room("Hall", width_m=None, depth_m=None)
    spec, notes = merge_to_spec(analysis([unknown]))
    assert spec["storeys"][0]["rooms"][0]["rect"][2:] == [3.5, 4.0]
    assert any("dimensions of 'Hall'" in q for q in notes["questions"]) and any("No dimensions" in q for q in notes["questions"])
    two = [room("A", width_m=None, depth_m=None), room("B", width_m=None, depth_m=None)]
    spec, notes = merge_to_spec(analysis(two, footprint_width_m=10.0, footprint_depth_m=5.0))
    xs = [r["rect"] for r in spec["storeys"][0]["rooms"]]
    assert max(r[0] + r[2] for r in xs) == pytest.approx(10.0) and max(r[1] + r[3] for r in xs) == pytest.approx(5.0)
    assert any("footprint" in q for q in notes["questions"])


def test_unplaceable_room_goes_beside_the_others_and_overlapping_openings_are_dropped():
    a = room("A", width_m=4.0, depth_m=4.0, doors=[{"wall": "e", "offset_m": 1.0, "width_m": 0.9}])
    b = room("B", width_m=4.0, depth_m=4.0, relative_to="A", side="e", doors=[{"wall": "w", "offset_m": 2.1, "width_m": 0.9}])
    c = room("C", width_m=3.0, depth_m=3.0, relative_to="Nowhere", side="n")
    spec, notes = merge_to_spec(analysis([a, b, c]))
    building_from_spec(spec)
    rects = {r["id"]: r["rect"] for r in spec["storeys"][0]["rooms"]}
    assert rects["b"][0] == 4.0 and rects["c"][0] == 8.0
    assert len(spec["storeys"][0]["openings"]) == 1 and any("did not fit" in q for q in notes["questions"])


def test_upper_storeys_repeat_when_photos_show_more_floors_than_plans():
    spec, notes = merge_to_spec(analysis(floors=2))
    assert len(spec["storeys"]) == 2 and building_from_spec(spec)
    ids = [r["id"] for s in spec["storeys"] for r in s["rooms"]]
    assert len(ids) == len(set(ids)) and any("upper floors repeat" in q for q in notes["questions"])


def test_building_pack_wall_colour_and_validation():
    spec = {"storeys": [{"name": "G", "rooms": [{"id": "a", "name": "A", "rect": [0, 0, 4, 4]}]}], "wall_color": "#112233"}
    walls = [p for p in building_from_spec(spec) if p["id"].endswith("-p0") and "wall" in p["id"]]
    assert walls and all(p["color"] == "#112233" for p in walls)
    default = [p for p in building_from_spec({**spec, "wall_color": None}) if "wall" in p["id"] and p["kind"] == "box"]
    assert all(p["color"] == "#e8e2d6" for p in default)
    with pytest.raises(BuildingSpecError, match="wall_color"):
        normalize({**spec, "wall_color": "beige"})
