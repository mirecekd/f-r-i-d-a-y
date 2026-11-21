# backend/tests/look_helpers.py
"""Fake browser and JPEG helpers shared by the workshop_look tests."""

import asyncio
import base64
import io

from PIL import Image

from app.workshop.look import SnapshotBroker


def jpeg_bytes() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (64, 48), "#884422").save(out, "JPEG")
    return out.getvalue()


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


class FakeBrowser:
    """Answers every snapshot request through `reply(req_msg) -> dict | None` (None: stays silent)."""

    def __init__(self, broker: SnapshotBroker, reply):
        self.broker, self.reply, self.requests, self.other = broker, reply, [], []

    async def emit(self, msg):
        if msg.get("t") != "workshop_snapshot_request":
            self.other.append(msg)
            return
        self.requests.append(msg)
        answer = self.reply(msg)
        if answer is not None:
            asyncio.get_running_loop().call_soon(self.broker.deliver, answer)


def good(msg):
    return {"t": "workshop_snapshot", "req": msg["req"], "id": msg["id"], "jpeg_b64": b64(jpeg_bytes())}
