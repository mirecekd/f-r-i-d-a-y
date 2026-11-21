# backend/tests/test_agent_model_default.py
"""Gemini agent catalog cutoff (MIN_GEMINI_GENERATION) and the dynamic default agent model."""

from types import SimpleNamespace

import pytest

from app.agent import agent_model, catalog_gemini, prefs
from app.agent.catalog import catalog


def gm(mid: str, name: str | None = None):
    return SimpleNamespace(name=f"models/{mid}", display_name=name or mid, supported_actions=["generateContent"], thinking=True)


ALL = [
    "gemini-1.5-pro", "gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro",
    "gemini-flash-latest", "gemini-pro-latest", "gemini-flash-lite-latest",
    "gemini-3-flash-preview", "gemini-3.1-pro-preview", "gemini-3.5-flash", "gemini-3.8-flash", "gemini-4-neon",
    "gemini-3.1-flash-tts", "embedding-001", "aqa", "learnlm-2.0-flash",
]  # fmt: skip


def test_cutoff_is_a_single_table_value():
    assert catalog_gemini.MIN_GEMINI_GENERATION == 3


def test_filter_text_drops_pre_3x_and_latest_aliases_and_non_agent_models():
    ids = [e["id"] for e in catalog_gemini.filter_text([gm(i) for i in ALL])]
    assert sorted(ids) == ["gemini-3-flash-preview", "gemini-3.1-pro-preview", "gemini-3.5-flash", "gemini-3.8-flash", "gemini-4-neon"]


def test_cutoff_follows_the_table(monkeypatch):
    monkeypatch.setattr(catalog_gemini, "MIN_GEMINI_GENERATION", 4)
    assert [e["id"] for e in catalog_gemini.filter_text([gm(i) for i in ALL])] == ["gemini-4-neon"]


def test_gemini_4_neon_is_flagged_high_only():
    label = catalog_gemini.filter_text([gm("gemini-4-neon", "Gemini 4 Neon")])[0]["label"]
    assert label == "Gemini 4 Neon (high thinking only)"


def test_newest_flash_by_version_number_stable_first():
    assert catalog_gemini.newest_flash(["gemini-3.5-flash", "gemini-3.10-flash", "gemini-3.8-flash", "gemini-3.1-pro-preview"]) == "gemini-3.10-flash"
    assert catalog_gemini.newest_flash(["gemini-3-flash-preview", "gemini-3.5-flash"]) == "gemini-3.5-flash"
    assert catalog_gemini.newest_flash(["gemini-3-flash-preview", "gemini-3.5-flash-preview"]) == "gemini-3.5-flash-preview"
    assert catalog_gemini.newest_flash(["gemini-3.5-flash-lite", "gemini-2.5-flash"]) is None


def with_entries(monkeypatch, gemini_ids: list[str], litellm_ids: list[str] | None = None):
    def e(i, p):
        return {"id": i, "provider": p, "label": i, "group": "g", "roles": ["agent"]}

    monkeypatch.setattr(
        catalog, "_entries", {"gemini": (0.0, [e(i, "gemini") for i in gemini_ids]), "litellm": (0.0, [e(i, "litellm") for i in litellm_ids or []])}
    )


def test_default_is_newest_flash_in_catalog_and_does_not_rot(monkeypatch):
    with_entries(monkeypatch, ["gemini-3.5-flash", "gemini-3.8-flash"])
    assert agent_model.resolve() == ("gemini-3.8-flash", None)
    with_entries(monkeypatch, ["gemini-3.5-flash", "gemini-3.9-flash"])
    assert agent_model.resolve() == ("gemini-3.9-flash", None)


def test_default_without_catalog_is_the_constant(monkeypatch):
    monkeypatch.setattr(catalog, "_entries", {})
    assert agent_model.resolve() == (agent_model.DEFAULT_MODEL, None)


def test_stale_pin_falls_back_with_the_old_id_for_the_notice(monkeypatch):
    with_entries(monkeypatch, ["gemini-3.8-flash"])
    prefs.save_model("agent", "gemini-3.1-pro-gone")
    assert agent_model.resolve() == ("gemini-3.8-flash", "gemini-3.1-pro-gone")
    prefs.save_model("agent", "gemini-2.5-pro")  # dropped by the generation cutoff
    assert agent_model.resolve() == ("gemini-3.8-flash", "gemini-2.5-pro")


def test_valid_pins_are_kept_and_an_empty_provider_catalog_does_not_invalidate(monkeypatch):
    with_entries(monkeypatch, ["gemini-3.8-flash"], ["eu.x.m"])
    prefs.save_model("agent", "eu.x.m")
    assert agent_model.resolve() == ("eu.x.m", None)
    with_entries(monkeypatch, ["gemini-3.8-flash"], [])  # litellm down: keep the pin
    assert agent_model.resolve() == ("eu.x.m", None)


@pytest.mark.parametrize("env", ["FRIDAY_AGENT_MODEL"])
def test_env_pin_is_used_when_nothing_is_stored(monkeypatch, env):
    with_entries(monkeypatch, ["gemini-3.8-flash"], ["eu.x.m"])
    monkeypatch.setenv(env, "eu.x.m")
    assert agent_model.resolve() == ("eu.x.m", None)
