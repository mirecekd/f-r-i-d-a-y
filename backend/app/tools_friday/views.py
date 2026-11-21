# backend/app/tools_friday/views.py
"""View tools: open and close rich floating panels in the browser."""

from typing import Any

from app.tools_friday.ctx import Ctx
from app.views import VIEW_KINDS, ViewError, view_close_msg, view_msg
from app.voice.tools import Tool, ToolRegistry

# Data shape per view kind (docs/protocol.md "View panels"); a test keeps the keys equal to VIEW_KINDS.
VIEW_DATA_SHAPES = {
    "image": "{url, alt?, caption?}",
    "chart": "{type: line|bar|pie|scatter|radar, labels?, datasets: [{label?, data: number[]}]}",
    "table": "{columns: string[], rows: any[][]}",
    "markdown": "{text}",
    "code": "{code, lang?}",
    "diagram": "{code} (mermaid source)",
    "map": "{center: [lat, lon], zoom?, markers?: [{lat, lon, label?}]}",
    "json": "{value}",
    "memory_graph": "{nodes: [{id, label, kind, weight, ts, project}], links: [{source, target, kind, weight}]}",
    "image_card": "{url, summary, kind, people_count, objects, text_found, exif, notes}",
    "file_card": "{id, name, kind, size, title, summary, meta, outline, tables?, text_excerpt, truncated, download_url} (use file_to_scene instead)",
}


def show_view_description() -> str:
    shapes = "; ".join(f"{k}: {VIEW_DATA_SHAPES[k]}" for k in sorted(VIEW_KINDS))
    return (
        "Show a floating panel next to the 3D scene: image, chart, table, markdown text, code, diagram, map "
        "or json. Use it for anything better seen than said: lists, comparisons, numbers, pictures, code. "
        "Reusing an id replaces that panel. Returns the panel id. "
        f"data by kind - {shapes}."
    )


def register_view_tools(registry: ToolRegistry, ctx: Ctx) -> None:
    async def show_view(args: dict[str, Any]) -> dict[str, Any]:
        data = args.get("data")
        if not isinstance(data, dict):
            return {"error": "data must be an object shaped for the view kind"}
        try:
            msg = view_msg(str(args.get("kind")), data, args.get("title"), args.get("id"))
        except ViewError as e:
            return {"error": str(e)}
        await ctx.emit(msg)
        return {"ok": True, "id": msg["id"]}

    async def close_view(args: dict[str, Any]) -> dict[str, Any]:
        view_id = args.get("id")
        if not isinstance(view_id, str) or not view_id:
            return {"error": "id must be the id of an open view"}
        await ctx.emit(view_close_msg(view_id))
        return {"ok": True}

    registry.register(Tool(
        "show_view", show_view_description(),
        {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": sorted(VIEW_KINDS)},
                "data": {"type": "object", "description": "Payload for the kind"},
                "title": {"type": "string"},
                "id": {"type": "string", "description": "Optional; reuse to replace a panel"},
            },
            "required": ["kind", "data"],
        },
        show_view,
    ))
    registry.register(Tool(
        "close_view", "Close a floating panel by the id show_view returned. Use when the user asks to dismiss it.",
        {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]},
        close_view,
    ))
