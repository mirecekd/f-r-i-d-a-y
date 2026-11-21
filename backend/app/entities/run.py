# backend/app/entities/run.py
"""entity_run: run the tool a tool entity stands for on the stored items linked to it, via the normal tool path."""

from typing import Any

from app.approval import Approvals
from app.entities.links import linked_entities
from app.tools_friday.ctx import Ctx
from app.voice.tools import ToolRegistry

REF_TYPES = ("file", "image")


def accepts_ref(registry: ToolRegistry) -> list[str]:
    return sorted(n for n, t in registry.tools.items() if "ref" in t.parameters.get("properties", {}))


async def run_tool_entity(ctx: Ctx, registry: ToolRegistry, approvals: Approvals, entity_id: object) -> dict[str, Any]:
    obj = next((o for o in ctx.scene.objects() if o["id"] == entity_id and o["kind"] == "entity"), None)
    if obj is None or (obj.get("ref") or {}).get("type") != "tool":
        return {"error": "entity_run needs the id of a tool entity (ref.type 'tool'); call entity_list"}
    name = obj["ref"]["id"]
    tool = registry.tools.get(name)
    if tool is None:
        return {"error": f"tool '{name}' is not registered"}
    if "ref" not in tool.parameters.get("properties", {}):
        return {"error": f"tool '{name}' takes no ref input; tools that accept refs: {', '.join(accepts_ref(registry))}"}
    refs = [e["ref"] for e in linked_entities(ctx.scene, obj["id"]) if (e.get("ref") or {}).get("type") in REF_TYPES]
    if not refs:
        return {"error": "link at least one file or image entity to the tool entity first (entity_link)"}
    results: list[dict[str, Any]] = []
    for ref in refs:
        args = {"ref": ref}
        if tool.risky:
            summary = tool.confirm_summary(args) if tool.confirm_summary else f"Run {name} on {ref['type']} {ref['id']}"
            if not await approvals.ask(name, summary, args):
                results.append({"ref": ref, "error": "denied by user"})
                continue
        results.append({"ref": ref, "result": await tool.handler(args)})
    return {"ok": True, "tool": name, "results": results}
