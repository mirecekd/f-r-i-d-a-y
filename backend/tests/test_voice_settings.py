# backend/tests/test_voice_settings.py
"""Language and voice pinning: prefs persistence, voices table, prompt builder, protocol validation, Live config."""

import json

import pytest
from fastapi.testclient import TestClient

from app import main
from app.agent import prefs
from app.agent.catalog import catalog
from app.agent.prompt import chat_prompt
from app.voice import language, session, voices
from app.voice.prompt import build_prompt
from app.voice.tools import ToolRegistry

ENTRIES = [
    {"id": "g1-live", "provider": "gemini", "label": "G1 Live", "group": "google live", "roles": ["chat"]},
    {"id": "g2-live", "provider": "gemini", "label": "G2 Live", "group": "google live", "roles": ["chat"]},
    {"id": "l1", "provider": "litellm", "label": "L1", "group": "x", "roles": ["agent"]},
]


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("FRIDAY_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("GEMINI_LANGUAGE", raising=False)
    monkeypatch.delenv("GEMINI_VOICE", raising=False)
    monkeypatch.delenv("GEMINI_LIVE_MODEL", raising=False)
    return tmp_path


def test_language_defaults_to_czech_and_persists():
    assert prefs.language() is None and language.current_language() == "cs-CZ"
    prefs.save_language("de-DE")
    assert prefs.language() == "de-DE" and language.current_language() == "de-DE"


def test_language_env_fallback_and_unknown_pin_ignored(monkeypatch):
    monkeypatch.setenv("GEMINI_LANGUAGE", "pl-PL")
    assert language.current_language() == "pl-PL"
    prefs.save_language("xx-XX")
    assert language.current_language() == "pl-PL"


def test_voice_persisted_per_model_and_keeps_other_keys(data_dir):
    prefs.save_model("chat", "m1")
    prefs.save_voice("m1", "Leda")
    prefs.save_voice("m2", "Puck")
    assert prefs.voice_for("m1") == "Leda" and prefs.voice_for("m2") == "Puck" and prefs.voice_for("m3") is None
    assert json.loads((data_dir / "prefs.json").read_text())["chat_model"] == "m1"
    assert prefs.load()["chat_model"] == "m1"


def test_voice_falls_back_to_default_when_pin_invalid(monkeypatch):
    prefs.save_voice("m1", "Nope")
    assert voices.current_voice("m1") == voices.DEFAULT_VOICE == "Kore"
    monkeypatch.setitem(voices.MODEL_VOICES, "m1", ["Puck", "Charon"])
    prefs.save_voice("m1", "Kore")  # valid in general but not for this model
    assert voices.current_voice("m1") == "Puck"
    assert [v["id"] for v in voices.voices_for("m1")] == ["Puck", "Charon"]


def test_voices_table_is_complete_and_well_formed():
    ids = [v["id"] for v in voices.VOICES]
    assert len(ids) == len(set(ids)) == 30
    assert all(v["gender"] in ("female", "male") and v["style"] and v["label"] for v in voices.VOICES)
    default = next(v for v in voices.VOICES if v["id"] == voices.DEFAULT_VOICE)
    assert default["gender"] == "female"


def test_prompt_boss_rule_only_for_czech():
    cs = build_prompt("cs-CZ", "Czech")
    assert "Šéfe" in cs and "Friday, ..." in cs and "udělala jsem" in cs and "Rozuměj uživateli česky" in cs
    de = build_prompt("de-DE", "German")
    assert de.startswith("Answer in German unless the user switches language.") and "Šéfe" not in de
    assert "Šéfe" in chat_prompt("cs-CZ") and "Šéfe" not in chat_prompt("fr-FR")
    assert chat_prompt("fr-FR").startswith("Answer in French")


def test_live_config_uses_pinned_language_voice_and_vad():
    prefs.save_model("chat", "g1-live")
    prefs.save_language("de-DE")
    prefs.save_voice("g1-live", "Leda")
    cfg = session.build_config(ToolRegistry())
    assert cfg.speech_config and cfg.speech_config.language_code == "de-DE"
    assert cfg.speech_config.voice_config.prebuilt_voice_config.voice_name == "Leda"  # type: ignore[union-attr]
    assert str(cfg.system_instruction).startswith("Answer in German")
    assert cfg.input_audio_transcription is not None and cfg.input_audio_transcription.language_codes == ["de-DE"]
    assert cfg.realtime_input_config is not None
    vad = cfg.realtime_input_config.automatic_activity_detection
    assert vad is not None and vad.silence_duration_ms == 700 and vad.prefix_padding_ms == 200


def test_native_audio_model_drops_unsupported_language_code():
    assert language.speech_language("gemini-2.5-flash-native-audio-latest", "cs-CZ") is None
    assert language.speech_language("gemini-2.5-flash-native-audio-latest", "de-DE") == "de-DE"
    assert language.speech_language("gemini-3.8-live", "cs-CZ") == "cs-CZ"


@pytest.fixture
def client(monkeypatch):
    async def fake_get():
        return ENTRIES

    monkeypatch.setattr(catalog, "get", fake_get)
    monkeypatch.setattr(catalog, "_entries", {"all": (0.0, ENTRIES)})
    return TestClient(main.app)


def next_models(ws):
    while True:
        msg = ws.receive_json()
        if msg["t"] == "models":
            return msg


def test_models_message_shape_and_set_language_and_voice(client):
    with client.websocket_connect("/ws") as ws:
        first = next_models(ws)
        assert first["language"] == "cs-CZ" and first["voice"] == "Kore"
        assert {"code": "cs-CZ", "label": "Čeština"} in first["languages"]
        assert len(first["voices"]) == 30 and set(first["voices"][0]) == {"id", "label", "gender", "style"}
        ws.send_json({"t": "set_language", "language": "sk-SK"})
        assert next_models(ws)["language"] == "sk-SK"
        ws.send_json({"t": "set_model", "role": "chat", "model": "g1-live"})
        assert next_models(ws)["voice"] == "Kore"
        ws.send_json({"t": "set_voice", "voice": "Leda"})
        assert next_models(ws)["voice"] == "Leda"
        ws.send_json({"t": "set_model", "role": "chat", "model": "g2-live"})
        assert next_models(ws)["voice"] == "Kore"  # per-model pin: g2-live has none yet
        ws.send_json({"t": "set_model", "role": "chat", "model": "g1-live"})
        assert next_models(ws)["voice"] == "Leda"  # g1-live pin is remembered


def test_set_language_and_voice_reject_unknown_values(client):
    with client.websocket_connect("/ws") as ws:
        next_models(ws)
        ws.send_json({"t": "set_language", "language": "xx-XX"})
        assert "unknown language" in ws.receive_json()["message"]
        ws.send_json({"t": "set_voice", "voice": "Nobody"})
        assert "not available" in ws.receive_json()["message"]
    assert prefs.language() is None and prefs.voice_for("gemini-3.8-live") is None
