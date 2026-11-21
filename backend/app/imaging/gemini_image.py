# backend/app/imaging/gemini_image.py
"""Call a Gemini image model (images in, one image out); model choice with fallback, 90 s timeout, readable errors."""

import asyncio
import logging
import os
import re
from typing import Any

from google import genai
from google.genai import errors, types

log = logging.getLogger("friday.imaging")
PREFERENCE = ("gemini-3.1-flash-image", "gemini-2.5-flash-image")
TIMEOUT_S = 90
_IMAGE_MODEL = re.compile(r"^gemini-[a-z0-9.\-]*image[a-z0-9.\-]*$")
_BLOCKED = ("SAFETY", "PROHIBITED", "BLOCKLIST", "SPII", "RECITATION")
_chosen: str | None = None


class ImagingError(RuntimeError):
    """A failure whose message is safe to show to the user."""


def forget_choice() -> None:
    global _chosen
    _chosen = None


def override_model(name: str | None = None) -> str | None:
    """The explicit model from the `model` argument or FRIDAY_IMAGE_MODEL; only Gemini image model ids are accepted."""
    text = (name or os.getenv("FRIDAY_IMAGE_MODEL") or "").strip().removeprefix("models/")
    if not text:
        return None
    if not _IMAGE_MODEL.match(text):
        raise ImagingError(f"{text[:60]!r} is not a Gemini image model id")
    return text


async def candidates(client: Any, name: str | None = None) -> list[str]:
    """Models to try in order: the override alone, else the cached choice, then the preference list that the live catalog has."""
    forced = override_model(name)
    if forced:
        return [forced]
    try:
        live = {str(m.name or "").removeprefix("models/") async for m in await client.aio.models.list()}
    except Exception as e:
        log.warning("image model listing failed: %s", type(e).__name__)
        live = set(PREFERENCE)
    order = [m for m in PREFERENCE if m in live] or list(PREFERENCE)
    if _chosen in order:
        order.remove(_chosen)
        order.insert(0, _chosen)
    return order


def block_reason(value: Any) -> str | None:
    text = str(getattr(value, "name", value) or "")
    return text if any(k in text.upper() for k in _BLOCKED) else None


def extract_image(resp: Any) -> tuple[bytes, str]:
    """The first image of a generate_content response; ImagingError (readable, says when blocked) when there is none."""
    reason = block_reason(getattr(getattr(resp, "prompt_feedback", None), "block_reason", None))
    if reason:
        raise ImagingError(f"the request was blocked by the model's safety filter ({reason})")
    said: list[str] = []
    finish = None
    for cand in resp.candidates or []:
        finish = finish or cand.finish_reason
        for part in (cand.content.parts if cand.content and cand.content.parts else []):
            inline = part.inline_data
            if inline and inline.data and str(inline.mime_type or "").startswith("image/"):
                return bytes(inline.data), str(inline.mime_type)
            if part.text:
                said.append(part.text.strip())
    if block_reason(finish):
        raise ImagingError(f"the result was blocked by the model's safety filter ({block_reason(finish)})")
    detail = f": {' '.join(said)[:200]}" if said else ""
    raise ImagingError(f"the model returned no image{detail}")


async def _call(client: Any, model: str, images: list[tuple[bytes, str]], prompt: str) -> Any:
    parts: list[Any] = [types.Part.from_bytes(data=d, mime_type=m) for d, m in images] + [types.Part(text=prompt)]
    config = types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"])
    return await client.aio.models.generate_content(model=model, contents=parts, config=config)


async def generate_image(
    images: list[tuple[bytes, str]], prompt: str, model: str | None = None
) -> tuple[str, bytes, str]:
    """Returns (model used, image bytes, mime). The images go to Gemini image models only, nowhere else."""
    global _chosen
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise ImagingError("GEMINI_API_KEY is not set")
    client = genai.Client(api_key=key)
    last = "no image model is available"
    for name in await candidates(client, model):
        try:
            resp = await asyncio.wait_for(_call(client, name, images, prompt), TIMEOUT_S)
        except TimeoutError as e:
            raise ImagingError(f"the image model did not answer within {TIMEOUT_S} s") from e
        except errors.APIError as e:
            last = f"{name}: {type(e).__name__} {getattr(e, 'code', '')}"
            log.warning("image model %s failed (%s), trying the next one", name, last)
            continue
        data, mime = extract_image(resp)
        _chosen = name
        return name, data, mime
    raise ImagingError(f"image generation failed ({last})")
