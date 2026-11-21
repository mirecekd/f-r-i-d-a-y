# backend/tests/test_selfecho.py
"""Self-echo detector, audio_profile storage, profile-dependent Live config and the relay hook."""

import asyncio

from google.genai import types

from app.voice import selfecho, session
from app.voice.bridge import VoiceBridge
from app.voice.relay import Relay
from app.voice.selfecho import EchoGuard, is_self_echo, normalise, similarity
from app.voice.tools import ToolRegistry

OWN = "Ahoj, jsem Friday a mohu ti nakreslit krychli."


def test_normalise_strips_case_diacritics_and_punctuation():
    assert normalise("  Ahoj,  ŠKOLA!! ") == "ahoj skola"


def test_identical_and_near_identical_text_is_echo():
    assert is_self_echo(OWN, OWN, 0.5)
    assert is_self_echo("ahoj jsem friday a mohu ti nakreslit krychly", OWN, 1.0)


def test_unrelated_text_is_not_echo():
    assert not is_self_echo("nakresli mi modrou kouli prosim", OWN, 0.5)
    assert similarity("", OWN) == 0.0


def test_long_fragment_of_own_output_is_echo_but_short_one_is_not():
    assert is_self_echo("jsem Friday a mohu ti nakreslit", OWN, 1.0)
    assert not is_self_echo("ahoj", OWN, 1.0)


def test_age_outside_window_is_not_echo():
    assert not is_self_echo(OWN, OWN, 3.5)
    assert not is_self_echo(OWN, OWN, -1.0)


def test_guard_remembers_last_output_only():
    g = EchoGuard()
    assert not g.is_echo(OWN, 0.0)
    g.remember(OWN, 10.0)
    assert g.is_echo(OWN, 12.0)
    assert not g.is_echo(OWN, 14.0)
    g.remember("   ", 20.0)
    assert g.is_echo(OWN, 21.0) is False  # blank text keeps the old memory, which is already stale


def test_threshold_constants():
    assert selfecho.THRESHOLD == 0.85 and selfecho.WINDOW_S == 3.0


def test_audio_profile_is_stored_and_validated():
    async def send(_):
        pass

    b = VoiceBridge(send, send, ToolRegistry())
    assert b.audio_profile == "headphones"
    assert b.set_audio_profile("speaker") and b.audio_profile == "speaker"
    assert not b.set_audio_profile("loudspeaker") and b.audio_profile == "speaker"
    assert not b.set_audio_profile(None)


def test_speaker_profile_selects_slower_turn_end():
    vad = session.activity_detection("speaker")
    assert (vad.silence_duration_ms, vad.prefix_padding_ms) == (900, 300)
    assert vad.end_of_speech_sensitivity == types.EndSensitivity.END_SENSITIVITY_LOW
    assert vad.start_of_speech_sensitivity == types.StartSensitivity.START_SENSITIVITY_LOW
    default = session.activity_detection()
    assert (default.silence_duration_ms, default.prefix_padding_ms) == (session.VAD_SILENCE_MS, session.VAD_PREFIX_MS)


def test_build_config_applies_profile_and_keeps_barge_in():
    for profile, silence in (("speaker", 900), ("headphones", session.VAD_SILENCE_MS)):
        cfg = session.build_config(ToolRegistry(), profile=profile)
        rt = cfg.realtime_input_config
        assert rt is not None and rt.automatic_activity_detection is not None
        assert rt.automatic_activity_detection.silence_duration_ms == silence
        assert rt.activity_handling == types.ActivityHandling.START_OF_ACTIVITY_INTERRUPTS


def content(**kw) -> types.LiveServerMessage:
    return types.LiveServerMessage(server_content=types.LiveServerContent(**kw))


def audio_msg() -> types.LiveServerMessage:
    part = types.Part(inline_data=types.Blob(data=b"\x01\x02", mime_type="audio/pcm"))
    return types.LiveServerMessage(server_content=types.LiveServerContent(model_turn=types.Content(parts=[part])))


def test_relay_drops_echo_turn_and_notifies_once():
    sent: list[dict] = []
    audio: list[bytes] = []

    async def send_json(m):
        sent.append(m)

    async def send_bytes(b):
        audio.append(b)

    async def go():
        r = Relay(send_json, send_bytes, lambda: False)
        out = types.Transcription(text=OWN)
        await r.on_content(content(output_transcription=out))
        await r.on_content(content(input_transcription=types.Transcription(text=OWN)))
        await r.on_content(audio_msg())
        await r.on_content(content(turn_complete=True))
        # a second echo in a later turn: dropped again, but no second notice
        await r.on_content(content(output_transcription=out))
        await r.on_content(content(input_transcription=types.Transcription(text=OWN)))
        await r.on_content(content(turn_complete=True))
        # genuine speech after echo is shown normally
        await r.on_content(content(input_transcription=types.Transcription(text="nakresli kouli")))

    asyncio.run(go())
    assert audio == []  # the answer to the echo was never forwarded
    notices = [m for m in sent if m["t"] == "notice"]
    assert notices == [{"t": "notice", "text": "Ozvena potlacena"}]
    user = [m for m in sent if m["t"] == "transcript" and m["role"] == "user"]
    assert [m["text"] for m in user] == ["nakresli kouli"]
