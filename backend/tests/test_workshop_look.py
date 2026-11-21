# backend/tests/test_workshop_look.py
"""SnapshotBroker against a hostile fake browser (no network)."""

import asyncio

import pytest

from app.workshop import look
from app.workshop.look import NO_ANSWER, SnapshotBroker, decode_jpeg
from app.workshop.store import WorkshopError
from tests.look_helpers import FakeBrowser, b64, good, jpeg_bytes
from tests.vision_helpers import png_bytes


def ask(broker, browser, wid="w1", timeout=1.0):
    return asyncio.run(broker.request(browser.emit, wid, 640, timeout))


def test_happy_path_returns_jpeg_and_sends_a_well_formed_request():
    broker = SnapshotBroker()
    browser = FakeBrowser(broker, good)
    assert ask(broker, browser).startswith(b"\xff\xd8\xff")
    sent = browser.requests[0]
    assert sent["id"] == "w1" and sent["width"] == 640 and len(sent["req"]) == 16
    assert broker._pending == {}


def test_timeout_has_the_clear_message_and_leaves_nothing_pending():
    broker = SnapshotBroker()
    with pytest.raises(WorkshopError, match="the browser did not answer"):
        ask(broker, FakeBrowser(broker, lambda m: None), timeout=0.05)
    assert NO_ANSWER == "the browser did not answer (the tab may be in the background)"
    assert broker._pending == {}


@pytest.mark.parametrize(
    ("reply_b64", "text"),
    [
        ("@@not base64@@", "not valid base64"),
        (b64(b"PNG\x89 not a jpeg at all"), "not a JPEG"),
        (b64(b"\xff\xd8\xff" + b"0" * look.MAX_BYTES), "larger than 800 kB"),
        ("A" * (look.MAX_B64_CHARS + 8), "larger than 800 kB"),
        ("", "no image"),
        (12345, "no image"),
    ],
)
def test_hostile_payloads_fail_the_waiting_request_clearly(reply_b64, text):
    broker = SnapshotBroker()
    browser = FakeBrowser(broker, lambda m: {"t": "workshop_snapshot", "req": m["req"], "id": m["id"], "jpeg_b64": reply_b64})
    with pytest.raises(WorkshopError, match=text):
        ask(broker, browser)


def test_browser_error_reply_becomes_a_workshop_error():
    broker = SnapshotBroker()
    browser = FakeBrowser(broker, lambda m: {"t": "workshop_snapshot", "req": m["req"], "id": m["id"], "error": "hidden"})
    with pytest.raises(WorkshopError, match="could not take the snapshot"):
        ask(broker, browser)


def test_foreign_workshop_id_and_unknown_req_are_ignored_then_real_reply_wins():
    broker = SnapshotBroker()

    def reply(msg):
        broker.deliver({"t": "workshop_snapshot", "req": msg["req"], "id": "other", "jpeg_b64": b64(jpeg_bytes())})
        broker.deliver({"t": "workshop_snapshot", "req": "old", "id": msg["id"], "jpeg_b64": b64(jpeg_bytes())})
        broker.deliver({"t": "workshop_snapshot", "req": ["x"], "id": ["y"]})
        broker.deliver({})
        return good(msg)

    assert ask(broker, FakeBrowser(broker, reply)).startswith(b"\xff\xd8")


def test_duplicate_reply_and_flood_after_completion_are_dropped():
    broker = SnapshotBroker()

    def reply(msg):
        return good(msg)

    async def go():
        browser = FakeBrowser(broker, reply)
        data = await broker.request(browser.emit, "w1", 800, 1.0)
        for _ in range(500):  # a flood of replies for the finished request
            broker.deliver(good(browser.requests[0]))
        return data

    assert asyncio.run(go()).startswith(b"\xff\xd8")
    assert broker._pending == {}


def test_too_many_waiting_requests_are_refused_and_cancel_all_fails_the_rest():
    broker = SnapshotBroker()

    async def go():
        silent = FakeBrowser(broker, lambda m: None)
        waiting = [asyncio.create_task(broker.request(silent.emit, "w1", 800, 5.0)) for _ in range(look.MAX_PENDING)]
        await asyncio.sleep(0.01)
        with pytest.raises(WorkshopError, match="too many"):
            await broker.request(silent.emit, "w1", 800, 5.0)
        broker.cancel_all()
        results = await asyncio.gather(*waiting, return_exceptions=True)
        return results

    results = asyncio.run(go())
    assert len(results) == look.MAX_PENDING
    assert all(isinstance(r, WorkshopError) and "closed" in str(r) for r in results)
    assert broker._pending == {}


def test_decode_jpeg_accepts_a_jpeg_and_rejects_png():
    assert decode_jpeg(b64(jpeg_bytes()))
    with pytest.raises(WorkshopError, match="not a JPEG"):
        decode_jpeg(b64(png_bytes()))


