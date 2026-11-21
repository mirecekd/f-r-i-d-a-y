# backend/tests/test_frames.py
"""FrameForwarder: caps, rate limit, inactive session, bad input; plus the bridge hook."""

import asyncio
import base64
from typing import Any

from app.voice import ToolRegistry, VoiceBridge
from app.voice.frames import MAX_FRAME_BYTES, FrameForwarder

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100


def frame(data: bytes = JPEG, **over: Any) -> dict:
    return {"t": "frame", "source": "camera", "mime": "image/jpeg", "data_b64": base64.b64encode(data).decode(), **over}


class FakeLive:
    def __init__(self) -> None:
        self.sent: list[Any] = []

    async def send_realtime_input(self, **kw):
        self.sent.append(kw)

    async def send_client_content(self, **kw):
        self.sent.append({"content": kw})


def tags(live: FakeLive) -> list[tuple[str, bool]]:
    return [(c["content"]["turns"].parts[0].text, c["content"]["turn_complete"]) for c in live.sent if "content" in c]


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def make(session: FakeLive | None):
    clock = Clock()
    return FrameForwarder(lambda: session, clock), clock


def test_forwards_jpeg_as_video_blob():
    live = FakeLive()
    fwd, _ = make(live)
    assert asyncio.run(fwd.handle(frame(source="screen"))) is True
    blob = live.sent[1]["video"]
    assert blob.data == JPEG and blob.mime_type == "image/jpeg"


def test_dropped_without_session():
    fwd, _ = make(None)
    assert asyncio.run(fwd.handle(frame())) is False
    assert fwd.dropped == 1 and fwd.forwarded == 0


def test_rate_limit_two_fps_and_stop_resets():
    async def go():
        live = FakeLive()
        fwd, clock = make(live)
        assert await fwd.handle(frame())
        clock.now += 0.2
        assert not await fwd.handle(frame())
        clock.now += 0.3
        assert await fwd.handle(frame())
        assert len(live.sent) == 3  # one tag, two frames
        clock.now += 0.1
        await fwd.handle({"t": "frames_stop"})
        assert await fwd.handle(frame())
        assert len(live.sent) == 5  # stop forgets the tag

    asyncio.run(go())


def test_size_cap():
    async def go():
        live = FakeLive()
        fwd, _ = make(live)
        assert not await fwd.handle(frame(b"\xff\xd8" + b"\x00" * MAX_FRAME_BYTES))
        assert not await fwd.handle({**frame(), "data_b64": "A" * (MAX_FRAME_BYTES * 2)})
        assert await fwd.handle(frame(b"\xff\xd8" + b"\x00" * (MAX_FRAME_BYTES - 2)))
        assert len(live.sent) == 2

    asyncio.run(go())


def test_rejects_malformed_frames():
    async def go():
        live = FakeLive()
        fwd, clock = make(live)
        bad = [
            frame(source="mic"),
            frame(mime="image/png"),
            frame(b"GIF89a"),
            {**frame(), "data_b64": "not base64!!"},
            {**frame(), "data_b64": 12},
            {"t": "frame"},
        ]
        for msg in bad:
            clock.now += 1
            assert not await fwd.handle(msg)
        assert not live.sent and fwd.dropped == len(bad)

    asyncio.run(go())


def test_send_failure_is_swallowed():
    class Broken:
        async def send_realtime_input(self, **_):
            raise RuntimeError("closed")

    fwd, _ = make(Broken())  # type: ignore[arg-type]
    assert asyncio.run(fwd.handle(frame())) is False


def test_bridge_without_voice_session_drops_frames():
    async def noop(_m):
        pass

    bridge = VoiceBridge(noop, noop, ToolRegistry())
    assert asyncio.run(bridge.frames.handle(frame())) is False


def test_source_tag_sent_once_per_source_without_triggering_a_reply():
    async def go():
        live = FakeLive()
        fwd, clock = make(live)
        for source in ("camera", "camera", "screen", "screen", "camera"):
            clock.now += 1
            assert await fwd.handle(frame(source=source))
        assert tags(live) == [
            ("[IMAGE SOURCE: WEBCAM]", False),
            ("[IMAGE SOURCE: SCREEN]", False),
            ("[IMAGE SOURCE: WEBCAM]", False),
        ]
        assert sum("video" in s for s in live.sent) == 5

    asyncio.run(go())


def test_source_tag_resent_for_a_new_session():
    async def go():
        sessions = [FakeLive(), FakeLive()]
        current = [sessions[0]]
        clock = Clock()
        fwd = FrameForwarder(lambda: current[0], clock)
        assert await fwd.handle(frame())
        clock.now += 1
        current[0] = sessions[1]  # reconnect
        assert await fwd.handle(frame())
        assert len(tags(sessions[0])) == 1 and len(tags(sessions[1])) == 1

    asyncio.run(go())


def test_tag_failure_still_forwards_the_frame():
    class NoTags(FakeLive):
        async def send_client_content(self, **kw):
            raise RuntimeError("tag refused")

    live = NoTags()
    fwd, _ = make(live)
    assert asyncio.run(fwd.handle(frame())) is True
    assert "video" in live.sent[0]
