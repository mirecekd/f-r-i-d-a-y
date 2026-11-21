# backend/app/imaging/compare.py
"""image_compare: show two stored images (before and after) as two image panels."""

from typing import Any

from app.tools_friday.ctx import Ctx
from app.views import ViewError, view_msg
from app.vision import store


async def _show(ctx: Ctx, label: str, meta: dict[str, Any]) -> None:
    data = {"url": store.url_of(meta), "alt": label, "caption": f"{label}: {meta['name']}"}
    await ctx.emit(view_msg("image", data, label, f"compare-{label.lower()}"))


async def compare_images(ctx: Ctx, a_id: Any, b_id: Any) -> dict[str, Any]:
    before, after = store.resolve(a_id), store.resolve(b_id)
    if before is None or after is None:
        return {"error": "unknown image id; call list_images"}
    try:
        await _show(ctx, "Before", before)
        await _show(ctx, "After", after)
    except ViewError as e:
        return {"error": str(e)[:200]}
    return {"ok": True, "before": {"image_id": before["id"], "url": store.url_of(before)},
            "after": {"image_id": after["id"], "url": store.url_of(after)},
            "derived": (after.get("derived") or {}).get("derived_from")}
