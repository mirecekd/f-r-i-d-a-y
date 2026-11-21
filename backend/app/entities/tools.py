# backend/app/entities/tools.py
"""Model tools for entities and their links: entity_link, entity_unlink, entity_list, entity_open, entity_arrange, entity_run."""

from typing import Any

from app.approval import Approvals
from app.entities.layout import arrange
from app.entities.links import links_of, make_link
from app.entities.open import find_entity, open_card
from app.entities.run import run_tool_entity
from app.files.service import FileService
from app.scene_schema import SceneError
from app.tools_friday.ctx import Ctx
from app.vision.service import VisionService
from app.voice.tools import Tool, ToolRegistry

TWEEN_MS = 700
_ID = {"id": {"type": "string", "description": "entity id from entity_list, e.g. ent-file-1a2b3c4d"}}


def describe_entities(ctx: Ctx) -> str:
    """Compact text: one line per entity (id, shape, title, ref, position, links)."""
    scene_links = links_of(ctx.scene)
    lines = []
    for o in ctx.scene.objects():
        if o["kind"] != "entity":
            continue
        ref = o.get("ref")
        links = [f"{k['id']}->{k['to'] if k['from'] == o['id'] else k['from']}" for k in scene_links if o["id"] in (k["from"], k["to"])]
        pos = ",".join(f"{v:g}" for v in o.get("pos", [0, 0, 0]))
        lines.append(f"{o['id']} {o['shape']} \"{o['title']}\" ref={ref['type'] + ':' + ref['id'] if ref else '-'} pos({pos})"
                     + (f" links[{' '.join(links)}]" if links else ""))
    return "\n".join(lines) or "no entities in the scene"


def register_entity_tools(
    registry: ToolRegistry, ctx: Ctx, vision: VisionService, files: FileService, approvals: Approvals
) -> None:
    async def apply(ops: list[dict[str, Any]]) -> dict[str, Any] | None:
        try:
            ctx.scene.apply(ops)
        except SceneError as e:
            return {"error": str(e)}
        await ctx.emit({"t": "scene", "ops": ops})
        return None

    async def entity_link(args: dict[str, Any]) -> dict[str, Any]:
        try:
            ops, lid = make_link(ctx.scene, str(args.get("from_id")), str(args.get("to_id")), args.get("label"), args.get("style"))
        except SceneError as e:
            return {"error": str(e)}
        return await apply(ops) or {"ok": True, "link_id": lid}

    async def entity_unlink(args: dict[str, Any]) -> dict[str, Any]:
        lid = args.get("link_id")
        if not any(o["id"] == lid for o in links_of(ctx.scene)):
            return {"error": "unknown link_id; call entity_list"}
        return await apply([{"op": "del", "id": str(lid)}]) or {"ok": True}

    async def entity_list(args: dict[str, Any]) -> dict[str, Any]:
        return {"entities": describe_entities(ctx)}

    async def entity_open(args: dict[str, Any]) -> dict[str, Any]:
        return await open_card(ctx, vision, files, args.get("id"))

    async def entity_arrange(args: dict[str, Any]) -> dict[str, Any]:
        layout = args.get("layout")
        if layout not in ("arc", "grid", "around"):
            return {"error": "layout must be arc, grid or around"}
        ents = [o for o in ctx.scene.objects() if o["kind"] == "entity"]
        center = None
        if layout == "around":
            hub = find_entity(ctx, args.get("center_id"))
            if hub is None:
                return {"error": "layout 'around' needs center_id of an existing entity"}
            center = list(hub.get("pos", [0, 0, 0]))
            ents = [o for o in ents if o["id"] != hub["id"]]
        if not ents:
            return {"error": "no entities to arrange"}
        spots = arrange(len(ents), layout, center)
        ops = [{"op": "set", "id": o["id"], "props": {"pos": p}, "ms": TWEEN_MS} for o, p in zip(ents, spots, strict=True)]
        return await apply(ops) or {"ok": True, "moved": len(ops)}

    async def entity_run(args: dict[str, Any]) -> dict[str, Any]:
        return await run_tool_entity(ctx, registry, approvals, args.get("tool_entity_id"))

    def add(name: str, description: str, props: dict[str, Any], required: list[str], handler: Any) -> None:
        registry.register(Tool(name, description, {"type": "object", "properties": props, "required": required}, handler))

    add("entity_link", "Connect two scene objects (usually entities) with a glowing link line, e.g. a file to a tool.",
        {"from_id": {"type": "string"}, "to_id": {"type": "string"}, "label": {"type": "string"},
         "style": {"type": "string", "enum": ["solid", "dashed"]}}, ["from_id", "to_id"], entity_link)
    add("entity_unlink", "Remove a link (the entities stay).", {"link_id": {"type": "string"}}, ["link_id"], entity_unlink)
    add("entity_list", "List the entities (files, images, tools) in the 3D scene with ids, shapes, titles, refs, positions and links.",
        {}, [], entity_list)
    add("entity_open", "Open the readable 2D card of an entity's stored file or image.", _ID, ["id"], entity_open)
    add("entity_arrange", "Re-layout all entities with a smooth glide: arc, grid, or around a centre entity.",
        {"layout": {"type": "string", "enum": ["arc", "grid", "around"]}, "center_id": {"type": "string"}}, ["layout"], entity_arrange)
    add("entity_run", "Run the tool a tool entity stands for on the files and images linked to it (risky tools ask the user first).",
        {"tool_entity_id": {"type": "string"}}, ["tool_entity_id"], entity_run)
