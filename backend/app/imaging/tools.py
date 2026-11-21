# backend/app/imaging/tools.py
"""Model tools of the imaging package: image_edit, image_compare, house_from_sources, house_refine."""

from collections.abc import Callable
from typing import Any

from app.imaging.compare import compare_images
from app.imaging.edit import edit_images
from app.imaging.prompts import OPERATIONS
from app.imaging.tools_house import register_house_tools
from app.model3d.session import ModelSession
from app.tools_friday.ctx import Ctx
from app.voice.tools import Tool, ToolRegistry

_IDS = {"type": "array", "items": {"type": "string"}, "description": "image ids from list_images or image_ready (8+ char prefix works)"}


def register_imaging_tools(registry: ToolRegistry, ctx: Ctx, models: ModelSession, model_for: Callable[[], str]) -> None:
    async def image_edit(args: dict[str, Any]) -> dict[str, Any]:
        return await edit_images(ctx, args.get("image_ids"), args.get("instruction"), str(args.get("operation") or "custom"),
                                 args.get("model"), bool(args.get("full_res")))

    async def image_compare(args: dict[str, Any]) -> dict[str, Any]:
        return await compare_images(ctx, args.get("a_id"), args.get("b_id"))

    registry.register(Tool(
        "image_edit",
        "Edit or combine uploaded photos with a Gemini image model and store the result as a NEW image (it is shown via "
        "image_ready). Operations: merge_people (put the people of several photos into one group photo), enhance, "
        "remove_background, outpaint, custom. The originals are always kept. The result is AI-generated and may not "
        "preserve faces exactly: say so to the user. 1-6 images, takes 10-30 seconds.",
        {"type": "object", "properties": {
            "image_ids": _IDS, "instruction": {"type": "string", "description": "what to do, in the user's words (required)"},
            "operation": {"type": "string", "enum": list(OPERATIONS)},
            "full_res": {"type": "boolean", "description": "send the originals instead of the 1600 px copies"}},
         "required": ["image_ids", "instruction"]},
        image_edit, long=True, scheduling="WHEN_IDLE",
    ))
    registry.register(Tool(
        "image_compare",
        "Show an image and its edited version side by side as two panels (before / after). Originals are always kept.",
        {"type": "object", "properties": {"a_id": {"type": "string"}, "b_id": {"type": "string"}}, "required": ["a_id", "b_id"]},
        image_compare,
    ))
    register_house_tools(registry, models, model_for)
