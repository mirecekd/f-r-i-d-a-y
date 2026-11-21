# backend/tests/test_agent_prefs.py
import json

from app.agent import prefs


def test_load_defaults_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("FRIDAY_DATA_DIR", str(tmp_path / "data"))
    assert prefs.load() == {"agent_model": None, "chat_model": None}


def test_save_persists_and_roundtrips(tmp_path, monkeypatch):
    monkeypatch.setenv("FRIDAY_DATA_DIR", str(tmp_path / "data"))
    prefs.save_model("agent", "eu.anthropic.claude-opus-5")
    prefs.save_model("chat", "gemini-3.5-flash")
    assert prefs.load() == {"agent_model": "eu.anthropic.claude-opus-5", "chat_model": "gemini-3.5-flash"}
    assert json.loads((tmp_path / "data" / "prefs.json").read_text())["agent_model"] == "eu.anthropic.claude-opus-5"


def test_corrupt_file_falls_back_and_keeps_working(tmp_path, monkeypatch):
    monkeypatch.setenv("FRIDAY_DATA_DIR", str(tmp_path))
    (tmp_path / "prefs.json").write_text("{not json")
    assert prefs.load()["chat_model"] is None
    prefs.save_model("chat", "m")
    assert prefs.load()["chat_model"] == "m"
