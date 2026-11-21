# backend/app/imaging/house.py
"""Collect plans (PDF, images) and photos, run ONE multi-source Gemini analysis, return the validated JSON."""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from app.agent import llm
from app.agent.catalog import catalog
from app.agent.llm_gemini import chat_gemini
from app.files import store as file_store
from app.imaging.house_parse import parse_house, parse_refine
from app.imaging.house_prompt import ANALYSIS_PROMPT, REFINE_PROMPT, RETRY
from app.vision import store
from app.vision.capability import FALLBACK_MODEL
from app.vision.parse import AnalysisParseError

log = logging.getLogger("friday.imaging")
MAX_IMAGES = 8
MAX_PDFS = 3
MAX_PDF_BYTES = 15 * 1024 * 1024
TIMEOUT_S = 120


class SourceError(ValueError):
    """The given plans or photos cannot be used; the message is safe to show."""


def collect_sources(file_ids: Any, image_ids: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """Content parts (labelled text + inline data) and the stored ids used. PDFs come from the files store, images from vision."""
    files = file_ids if isinstance(file_ids, list) else []
    images = image_ids if isinstance(image_ids, list) else []
    if not files and not images:
        raise SourceError("give at least one plan (file_ids, PDF) or photo (image_ids)")
    if len(files) > MAX_PDFS or len(images) > MAX_IMAGES:
        raise SourceError(f"at most {MAX_PDFS} PDF plans and {MAX_IMAGES} images per call")
    parts: list[dict[str, Any]] = []
    used: list[str] = []
    for n, ref in enumerate(files, 1):
        meta = file_store.resolve(ref)
        if meta is None:
            raise SourceError(f"unknown file id {str(ref)[:40]!r}; call list_files")
        path = file_store.original_path(meta["id"])
        if meta["kind"] != "pdf" or path is None:
            raise SourceError(f"file {str(ref)[:40]!r} is not a PDF; give plans as PDF or image")
        if path.stat().st_size > MAX_PDF_BYTES:
            raise SourceError("a PDF plan is larger than 15 MB")
        parts += [{"type": "text", "text": f"Source P{n}: PDF document (plan or description)"},
                  llm.image_part(path.read_bytes(), "application/pdf")]
        used.append(meta["id"])
    for n, ref in enumerate(images, 1):
        meta = store.resolve(ref)
        if meta is None:
            raise SourceError(f"unknown image id {str(ref)[:40]!r}; call list_images")
        parts += [{"type": "text", "text": f"Source I{n}: image (floor plan, outside photo or inside photo - decide which)"},
                  llm.image_part(store.analysis_jpeg(meta["id"]), "image/jpeg")]
        used.append(meta["id"])
    return parts, used


async def pick_model(pinned: str) -> str:
    """The pinned agent model when it is a Gemini model (only Gemini receives PDFs and plans), else gemini-flash-latest."""
    if catalog.provider_of(pinned) is None:
        await catalog.get()
    return pinned if catalog.provider_of(pinned) == "gemini" else FALLBACK_MODEL


async def ask_json(system: str, content: list[dict[str, Any]], model: str, parse: Callable[[str], dict[str, Any]]) -> dict[str, Any]:
    """One Gemini call with a strict JSON answer; an invalid reply is retried once with the reason."""
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}, {"role": "user", "content": content}]
    for attempt in range(2):
        reply = (await asyncio.wait_for(chat_gemini(model, messages, []), TIMEOUT_S))["text"]
        try:
            return parse(reply)
        except AnalysisParseError as e:
            log.info("house analysis reply invalid (%s)", e)
            if attempt == 1:
                raise
            messages += [{"role": "assistant", "content": reply or "(empty)"}, {"role": "user", "content": RETRY.format(why=e)}]
    raise AnalysisParseError("unreachable")


async def analyze_sources(file_ids: Any, image_ids: Any, notes: str, pinned: str) -> tuple[dict[str, Any], list[str], str]:
    """(analysis, source ids, model). Everything is sent to Gemini only."""
    parts, used = await asyncio.to_thread(collect_sources, file_ids, image_ids)
    text = (notes or "").strip()[:2000]
    parts.insert(0, {"type": "text", "text": "User notes (context, may be in Czech): " + (text or "none")})
    model = await pick_model(pinned)
    return await ask_json(ANALYSIS_PROMPT, parts, model, parse_house), used, model


async def analyze_for_refine(image_ids: Any, rooms: dict[str, str], notes: str, pinned: str) -> dict[str, Any]:
    parts, _ = await asyncio.to_thread(collect_sources, [], image_ids)
    parts.insert(0, {"type": "text", "text": "User notes: " + ((notes or "").strip()[:2000] or "none")})
    listing = "; ".join(f"{rid}: {name}" for rid, name in rooms.items())
    return await ask_json(REFINE_PROMPT.replace("{rooms}", listing), parts, await pick_model(pinned), parse_refine)
