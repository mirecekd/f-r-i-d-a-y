# backend/app/voice/frames.py
"""Live vision input: camera or screen frames from the browser, forwarded to the Live session.

Browser message `{t:'frame', source:'camera'|'screen', mime:'image/jpeg', data_b64}` becomes
`session.send_realtime_input(video=Blob(jpeg))`. Frames are dropped silently (they are a stream, a
missing one costs nothing) when no Live session is connected, the frame is malformed or over
MAX_FRAME_BYTES, or the connection already sent MAX_FPS frames in the last second.
`{t:'frames_stop'}` ends a stream: the rate limiter is reset so the next stream starts at once.

The first frame of a stream, and the first frame after the source switches, is preceded by one text
context turn `[IMAGE SOURCE: WEBCAM|SCREEN]` sent with `send_client_content(turn_complete=False)`, which
adds context without making the model answer. The tag is re-sent after a reconnect (new session object).
"""

import base64
import binascii
import logging
import time
from collections.abc import Callable
from typing import Any

from google.genai import types

log = logging.getLogger("friday.voice.frames")

MAX_FRAME_BYTES = 400_000  # decoded JPEG
MAX_FPS = 2  # per connection, all sources together
SOURCES = ("camera", "screen")
MIME = "image/jpeg"
JPEG_MAGIC = b"\xff\xd8"
SOURCE_TAGS = {"camera": "[IMAGE SOURCE: WEBCAM]", "screen": "[IMAGE SOURCE: SCREEN]"}


class FrameForwarder:
    def __init__(self, get_session: Callable[[], Any], clock: Callable[[], float] = time.monotonic):
        self._get_session = get_session  # the current Live session, or None while idle or reconnecting
        self._clock = clock
        self._last_sent: float | None = None
        self._tagged: tuple[Any, str] | None = None  # (session, source) the model was last told about
        self.forwarded = 0
        self.dropped = 0

    async def handle(self, msg: dict[str, Any]) -> bool:
        """Process `frame` / `frames_stop`; True when a frame was forwarded to the model."""
        if msg.get("t") == "frames_stop":
            self._last_sent = None
            self._tagged = None
            log.info("frames stopped: %d forwarded, %d dropped", self.forwarded, self.dropped)
            return False
        jpeg = self._decode(msg)
        session = self._get_session()
        now = self._clock()
        if jpeg is None or session is None or self._too_soon(now):
            self.dropped += 1
            return False
        self._last_sent = now
        try:
            await self._tag_source(session, msg["source"])
            await session.send_realtime_input(video=types.Blob(data=jpeg, mime_type=MIME))
        except Exception as e:
            log.debug("frame dropped: %s", e)
            self.dropped += 1
            return False
        self.forwarded += 1
        return True

    async def _tag_source(self, session: Any, source: str) -> None:
        if self._tagged is not None and self._tagged[0] is session and self._tagged[1] == source:
            return
        try:
            await session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part(text=SOURCE_TAGS[source])]), turn_complete=False
            )
        except Exception as e:  # the frame itself is still worth sending
            log.debug("source tag dropped: %s", e)
            return
        self._tagged = (session, source)

    def _too_soon(self, now: float) -> bool:
        return self._last_sent is not None and now - self._last_sent < 1 / MAX_FPS

    @staticmethod
    def _decode(msg: dict[str, Any]) -> bytes | None:
        data = msg.get("data_b64")
        if msg.get("source") not in SOURCES or msg.get("mime") != MIME or not isinstance(data, str):
            return None
        if len(data) > MAX_FRAME_BYTES * 4 // 3 + 4:  # reject before decoding
            return None
        try:
            jpeg = base64.b64decode(data, validate=True)
        except (binascii.Error, ValueError):
            return None
        return jpeg if jpeg.startswith(JPEG_MAGIC) and len(jpeg) <= MAX_FRAME_BYTES else None
