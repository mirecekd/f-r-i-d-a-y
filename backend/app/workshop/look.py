# backend/app/workshop/look.py
"""Snapshot broker: asks the browser for one JPEG of the work table and hands the reply to the waiting request.

Every reply comes from the browser and is untrusted: wrong shapes, other workshops, unknown or repeated `req` ids are
ignored; a reply that matches a waiting request but is not a usable JPEG fails that request with a WorkshopError."""

import asyncio
import base64
import binascii
import secrets
from typing import Any

from app.tools_friday.ctx import Emit
from app.workshop.store import WorkshopError

MAX_BYTES = 800 * 1024
MAX_B64_CHARS = (MAX_BYTES + 2) // 3 * 4
MAX_PENDING = 4
JPEG_MAGIC = b"\xff\xd8\xff"
NO_ANSWER = "the browser did not answer (the tab may be in the background)"


def decode_jpeg(b64: object) -> bytes:
    """The JPEG bytes of a base64 string, or WorkshopError (not a string, too large, bad base64, not a JPEG)."""
    if not isinstance(b64, str) or not b64:
        raise WorkshopError("the snapshot reply carries no image")
    if len(b64) > MAX_B64_CHARS:
        raise WorkshopError("the snapshot is larger than 800 kB")
    try:
        raw = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise WorkshopError("the snapshot is not valid base64") from None
    if len(raw) > MAX_BYTES:
        raise WorkshopError("the snapshot is larger than 800 kB")
    if not raw.startswith(JPEG_MAGIC):
        raise WorkshopError("the snapshot is not a JPEG image")
    return raw


class SnapshotBroker:
    """One per workshop session. `request` waits for the matching `deliver`; at most MAX_PENDING requests wait at once."""

    def __init__(self) -> None:
        self._pending: dict[str, tuple[str, asyncio.Future[bytes]]] = {}

    async def request(self, emit: Emit, workshop_id: str, width: int = 800, timeout: float = 8.0) -> bytes:
        if len(self._pending) >= MAX_PENDING:
            raise WorkshopError("too many snapshot requests are waiting; try again in a moment")
        req = secrets.token_hex(8)
        fut: asyncio.Future[bytes] = asyncio.get_running_loop().create_future()
        self._pending[req] = (workshop_id, fut)
        try:
            await emit(
                {"t": "workshop_snapshot_request", "req": req, "id": workshop_id, "width": max(200, min(int(width), 1600))}
            )
            return await asyncio.wait_for(fut, timeout)
        except TimeoutError:
            raise WorkshopError(NO_ANSWER) from None
        finally:
            self._pending.pop(req, None)

    def deliver(self, msg: dict[str, Any]) -> None:
        """Resolve the request named by `msg['req']`. Never raises; anything that does not match a waiting request is dropped."""
        req = msg.get("req")
        entry = self._pending.get(req) if isinstance(req, str) else None
        if entry is None or entry[0] != msg.get("id"):
            return
        del self._pending[req]  # type: ignore[arg-type]  # entry exists, so req is a str
        fut = entry[1]
        if fut.done():
            return
        if "error" in msg:
            fut.set_exception(WorkshopError(f"the browser could not take the snapshot ({str(msg['error'])[:40]})"))
            return
        try:
            fut.set_result(decode_jpeg(msg.get("jpeg_b64")))
        except WorkshopError as e:
            fut.set_exception(e)

    def cancel_all(self) -> None:
        """Session close: every waiting request fails at once with a clear error."""
        pending, self._pending = self._pending, {}
        for _, fut in pending.values():
            if not fut.done():
                fut.set_exception(WorkshopError("the workshop was closed before the snapshot arrived"))
