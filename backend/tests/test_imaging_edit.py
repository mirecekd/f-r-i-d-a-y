# backend/tests/test_imaging_edit.py
"""image_edit / image_compare: derived provenance, caps and validation, model fallback, blocked content (Gemini faked)."""

import asyncio
import io

import pytest
from PIL import Image

from app.imaging import edit
from app.imaging.compare import compare_images
from app.imaging.gemini_image import ImagingError
from app.vision import store
from tests.imaging_helpers import FakeCtx, stored_image
from tests.vision_helpers import jpeg_with_gps, png_bytes


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def fake_gen(monkeypatch):
    calls = []

    async def fake(images, prompt, model=None):
        calls.append({"n": len(images), "prompt": prompt, "model": model, "mimes": [m for _, m in images]})
        return "gemini-3.1-flash-image", png_bytes((64, 48), "#00aa00"), "image/png"

    monkeypatch.setattr(edit, "generate_image", fake)
    return calls


def test_merge_stores_new_derived_image_and_emits_ready(fake_gen):
    async def go():
        a, b = await stored_image("#aa0000"), await stored_image("#0000aa")
        ctx = FakeCtx()
        res = await edit.edit_images(ctx, [a["id"], b["id"][:12]], "merge them", "merge_people")
        return a, b, ctx, res

    a, b, ctx, res = run(go())
    assert res["ok"] and res["image_id"] not in (a["id"], b["id"])
    meta = store.load_meta(res["image_id"])
    assert meta and meta["derived"] == {"derived_from": [a["id"], b["id"]], "instruction": "merge them",
                                         "operation": "merge_people", "model": "gemini-3.1-flash-image"}
    assert store.load_meta(a["id"]) and store.load_meta(b["id"])  # originals kept
    assert [m["t"] for m in ctx.msgs] == ["image_ready"] and ctx.msgs[0]["id"] == res["image_id"]
    assert "keep" in fake_gen[0]["prompt"].lower() and "merge them" in fake_gen[0]["prompt"]
    assert fake_gen[0]["mimes"] == ["image/jpeg", "image/jpeg"]  # the 1600 px analysis copies


def test_full_res_sends_originals(fake_gen):
    async def go():
        a = await stored_image()
        return await edit.edit_images(FakeCtx(), [a["id"]], "enhance it", "enhance", full_res=True)

    assert run(go())["ok"] and fake_gen[0]["mimes"] == ["image/png"]


@pytest.mark.parametrize("ids,instruction,operation,needle", [
    (["x"], "", "custom", "instruction is empty"),
    (["x"], "   ", "custom", "instruction is empty"),
    ([], "do", "custom", "non-empty"),
    (["x"] * 7, "do", "custom", "at most 6"),
    (["0" * 32], "do", "custom", "unknown image id"),
    (["x"], "do", "paint_it_red", "unknown operation"),
])
def test_validation_errors_are_readable(fake_gen, ids, instruction, operation, needle):
    res = run(edit.edit_images(FakeCtx(), ids, instruction, operation))
    assert needle in res["error"] and not fake_gen


def test_merge_people_needs_two_images(fake_gen):
    async def go():
        a = await stored_image()
        return await edit.edit_images(FakeCtx(), [a["id"]], "merge", "merge_people")

    assert "at least two" in run(go())["error"] and not fake_gen


def test_oversize_result_is_refused(monkeypatch):
    async def big(images, prompt, model=None):
        return "m", b"\x89PNG\r\n\x1a\n" + b"0" * (edit.MAX_BYTES + 1), "image/png"

    monkeypatch.setattr(edit, "generate_image", big)

    async def go():
        a = await stored_image()
        return await edit.edit_images(FakeCtx(), [a["id"]], "enhance", "enhance")

    assert "larger than 12 MB" in run(go())["error"]


def test_result_is_stored_without_exif():
    clean, mime = edit.clean_image(jpeg_with_gps(), "image/jpeg")
    assert mime == "image/jpeg" and not Image.open(io.BytesIO(clean)).getexif()


def test_edit_error_from_the_model_is_returned(monkeypatch):
    async def boom(images, prompt, model=None):
        raise ImagingError("the request was blocked by the model's safety filter (SAFETY)")

    monkeypatch.setattr(edit, "generate_image", boom)

    async def go():
        a = await stored_image()
        return await edit.edit_images(FakeCtx(), [a["id"]], "enhance", "enhance")

    assert "blocked" in run(go())["error"]


def test_compare_emits_two_image_views(fake_gen):
    async def go():
        a, b = await stored_image(), await stored_image("#ff0000")
        ctx = FakeCtx()
        return ctx, await compare_images(ctx, a["id"], b["id"]), await compare_images(ctx, a["id"], "nope")

    ctx, ok, bad = run(go())
    assert ok["ok"] and [m["id"] for m in ctx.msgs] == ["compare-before", "compare-after"]
    assert all(m["kind"] == "image" for m in ctx.msgs) and "error" in bad
