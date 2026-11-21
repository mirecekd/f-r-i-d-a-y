# backend/tests/test_vision_images.py
"""Image validation, EXIF parsing, analysis copy, storage and the HTTP upload/serve endpoints."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import main
from app.vision import images, store
from app.vision.images import ImageRejected, inspect_image
from tests.vision_helpers import jpeg_with_gps, png_bytes


def test_exif_gps_time_camera_are_parsed():
    insp = inspect_image(jpeg_with_gps(), "image/jpeg")
    assert insp.exif["camera_make"] == "FriCam" and insp.exif["camera_model"] == "X100"
    assert insp.exif["taken_at"] == "2024-05-01T10:20:30"
    assert insp.exif["orientation"] == 6
    assert insp.exif["lat"] == pytest.approx(50.09, abs=0.001)
    assert insp.exif["lon"] == pytest.approx(14.42, abs=0.001)
    assert set(insp.exif) <= {"camera_make", "camera_model", "taken_at", "orientation", "lat", "lon"}
    assert (insp.w, insp.h) == (300, 400)  # orientation 6 rotates the upright size


def test_analysis_copy_is_downscaled_jpeg():
    insp = inspect_image(png_bytes((4000, 1000)), "image/png")
    copy = Image.open(io.BytesIO(insp.analysis_jpeg))
    assert copy.format == "JPEG" and max(copy.size) == images.ANALYSIS_SIDE and (insp.w, insp.h) == (4000, 1000)


def test_non_image_with_image_mime_is_rejected():
    with pytest.raises(ImageRejected, match="not a jpeg"):
        inspect_image(b"<html><script>alert(1)</script></html>", "image/png")


def test_mime_must_match_content_and_be_allowed():
    with pytest.raises(ImageRejected, match="does not match"):
        inspect_image(png_bytes(), "image/jpeg")
    with pytest.raises(ImageRejected, match="not allowed"):
        inspect_image(png_bytes(), "image/svg+xml")


def test_truncated_image_is_rejected():
    with pytest.raises(ImageRejected, match="cannot be decoded"):
        inspect_image(png_bytes()[:60], "image/png")


def test_oversize_is_rejected():
    with pytest.raises(ImageRejected, match="larger than 12 MB"):
        inspect_image(b"\x89PNG\r\n\x1a\n" + b"0" * images.MAX_BYTES, "image/png")


def test_decompression_bomb_is_rejected(monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    with pytest.raises(ImageRejected, match="cannot be decoded"):
        inspect_image(png_bytes((200, 200)), "image/png")


@pytest.fixture
def client():
    return TestClient(main.app)


def test_http_upload_then_serve_with_safe_headers(client):
    resp = client.post("/api/upload", files={"file": ("a b.png", png_bytes(), "image/png")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["url"] == f"/api/uploads/{body['id']}.png" and (body["w"], body["h"]) == (320, 200)
    got = client.get(body["url"])
    assert got.status_code == 200 and got.content == png_bytes()
    assert got.headers["content-type"] == "image/png"
    assert got.headers["x-content-type-options"] == "nosniff"
    assert got.headers["content-disposition"] == "inline"
    assert "sandbox" in got.headers["content-security-policy"]
    meta = store.load_meta(body["id"])
    assert meta is not None and meta["name"] == "a b.png"


def test_http_upload_rejects_non_image_and_oversize(client):
    bad = client.post("/api/upload", files={"file": ("x.png", b"not an image", "image/png")})
    assert bad.status_code == 400 and "not a jpeg" in bad.json()["error"]
    big = client.post("/api/upload", files={"file": ("x.png", b"\x89PNG\r\n\x1a\n" + b"0" * images.MAX_BYTES, "image/png")})
    assert big.status_code == 413


@pytest.mark.parametrize("name", ["../prefs.json", "..%2Fprefs.json", "a.png", "x" * 32 + ".png", "x.analysis.jpg"])
def test_serve_refuses_anything_but_uuid_names(client, name):
    store.uploads_dir().mkdir(parents=True, exist_ok=True)
    (store.uploads_dir() / "a.png").write_bytes(png_bytes())
    assert client.get(f"/api/uploads/{name}").status_code == 404


def test_original_is_stored_untouched(client):
    raw = jpeg_with_gps()
    body = client.post("/api/upload", files={"file": ("p.jpg", raw, "image/jpeg")}).json()
    assert (store.uploads_dir() / f"{body['id']}.jpg").read_bytes() == raw
    assert body["exif"]["lat"] == pytest.approx(50.09, abs=0.001)
