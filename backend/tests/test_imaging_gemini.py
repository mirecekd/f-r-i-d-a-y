# backend/tests/test_imaging_gemini.py
"""Gemini image model choice, fallback, env override, blocked and timeout handling (client faked)."""

import asyncio
from types import SimpleNamespace

import pytest
from google.genai import errors

from app.imaging import gemini_image
from app.imaging.gemini_image import ImagingError


def run(coro):
    return asyncio.run(coro)


class FakeModels:
    def __init__(self, names, behaviour):
        self.names, self.behaviour, self.used = names, behaviour, []

    async def list(self):
        async def gen():
            for n in self.names:
                yield SimpleNamespace(name=f"models/{n}")
        return gen()

    async def generate_content(self, model, contents, config):
        self.used.append(model)
        return self.behaviour(model)


def image_response(data=b"\x89PNGdata"):
    part = SimpleNamespace(inline_data=SimpleNamespace(data=data, mime_type="image/png"), text=None)
    return SimpleNamespace(prompt_feedback=None, candidates=[SimpleNamespace(finish_reason=None, content=SimpleNamespace(parts=[part]))])


def use_client(monkeypatch, models):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.delenv("FRIDAY_IMAGE_MODEL", raising=False)
    gemini_image.forget_choice()
    monkeypatch.setattr(gemini_image.genai, "Client", lambda api_key: SimpleNamespace(aio=SimpleNamespace(models=models)))


def test_prefers_3_1_and_caches_the_choice(monkeypatch):
    models = FakeModels(["gemini-2.5-flash-image", "gemini-3.1-flash-image"], lambda m: image_response())
    use_client(monkeypatch, models)
    name, data, mime = run(gemini_image.generate_image([(b"x", "image/png")], "p"))
    assert (name, mime) == ("gemini-3.1-flash-image", "image/png") and models.used == ["gemini-3.1-flash-image"]


def test_falls_back_to_2_5_when_the_newer_model_errors(monkeypatch):
    def behave(model):
        if "3.1" in model:
            raise errors.APIError(404, {"error": {"message": "gone", "status": "NOT_FOUND"}})
        return image_response()

    models = FakeModels(["gemini-2.5-flash-image", "gemini-3.1-flash-image"], behave)
    use_client(monkeypatch, models)
    assert run(gemini_image.generate_image([(b"x", "image/png")], "p"))[0] == "gemini-2.5-flash-image"
    assert models.used == ["gemini-3.1-flash-image", "gemini-2.5-flash-image"]
    models.used.clear()
    run(gemini_image.generate_image([(b"x", "image/png")], "p"))
    assert models.used[0] == "gemini-2.5-flash-image"  # the working model is cached first


def test_env_override_accepts_only_image_model_ids(monkeypatch):
    use_client(monkeypatch, FakeModels([], lambda m: image_response()))
    monkeypatch.setenv("FRIDAY_IMAGE_MODEL", "gpt-4o")
    with pytest.raises(ImagingError, match="not a Gemini image model"):
        run(gemini_image.generate_image([(b"x", "image/png")], "p"))
    monkeypatch.setenv("FRIDAY_IMAGE_MODEL", "gemini-3-pro-image")
    models = FakeModels([], lambda m: image_response())
    use_client(monkeypatch, models)
    monkeypatch.setenv("FRIDAY_IMAGE_MODEL", "gemini-3-pro-image")
    run(gemini_image.generate_image([(b"x", "image/png")], "p"))
    assert models.used == ["gemini-3-pro-image"]


def test_blocked_and_text_only_answers_are_readable():
    blocked = SimpleNamespace(prompt_feedback=SimpleNamespace(block_reason="PROHIBITED_CONTENT"), candidates=[])
    with pytest.raises(ImagingError, match="blocked by the model's safety filter"):
        gemini_image.extract_image(blocked)
    text = SimpleNamespace(inline_data=None, text="I cannot do that")
    refused = SimpleNamespace(prompt_feedback=None, candidates=[SimpleNamespace(finish_reason="STOP", content=SimpleNamespace(parts=[text]))])
    with pytest.raises(ImagingError, match="no image: I cannot do that"):
        gemini_image.extract_image(refused)


def test_timeout_is_reported(monkeypatch):
    async def slow(model):
        await asyncio.sleep(5)

    class Slow(FakeModels):
        async def generate_content(self, model, contents, config):
            await asyncio.sleep(5)

    use_client(monkeypatch, Slow(["gemini-3.1-flash-image"], None))
    monkeypatch.setattr(gemini_image, "TIMEOUT_S", 0.05)
    with pytest.raises(ImagingError, match="did not answer"):
        run(gemini_image.generate_image([(b"x", "image/png")], "p"))
