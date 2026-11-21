# backend/app/workshop/tools.py
"""Model tools of the workshop (one registration call per connection). Every failure comes back as {error}."""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from app.agent_settings import pinned_model
from app.tools_friday.ctx import Ctx
from app.voice.tools import Tool, ToolRegistry
from app.workshop.doc import SPEC_DOC
from app.workshop.look_tools import register_look_tool
from app.workshop.session import WORKSHOP_ERRORS, WorkshopSession
from app.workshop.sources_tools import register_sources_tool

Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
MAX_SPEC_REPLY = 12_000
NAME = {"type": "string", "description": "parameter name from the last workshop_build"}
BUILD_DESCRIPTION = (
    "Build or replace the object on the work table of the open workshop from a part tree (data, never code). "
    "The server validates it and draws it at once; an error names the bad field - fix that field and call again. "
    "Returns {parts, params (the sliders), notes}.\n\n" + SPEC_DOC
)


def _guarded(fn: Handler) -> Handler:
    async def run(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return await fn(args)
        except WORKSHOP_ERRORS as e:
            return {"error": str(e)[:600]}
        except (TypeError, KeyError, ValueError) as e:
            return {"error": f"bad arguments: {e}"[:300]}

    return run


def register_workshop_tools(registry: ToolRegistry, ctx: Ctx) -> WorkshopSession:
    """Create this connection's workshop session and register the workshop_* tools on `registry`."""
    session = WorkshopSession(ctx)

    async def open_(a: dict[str, Any]) -> dict[str, Any]:
        title = a.get("title") if isinstance(a.get("title"), str) else None
        return await session.open(a.get("id"), title)

    async def build(a: dict[str, Any]) -> dict[str, Any]:
        return await session.build(a.get("spec"))

    async def param(a: dict[str, Any]) -> dict[str, Any]:
        return await session.param(a.get("name"), a.get("value"))

    async def undo(a: dict[str, Any]) -> dict[str, Any]:
        return await session.step(True)

    async def redo(a: dict[str, Any]) -> dict[str, Any]:
        return await session.step(False)

    async def close(a: dict[str, Any]) -> dict[str, Any]:
        return await session.leave()

    async def view_source(a: dict[str, Any]) -> dict[str, Any]:
        rec = session.require()
        text = json.dumps(rec["spec"], ensure_ascii=False, separators=(",", ":")) if rec["spec"] else "null"
        return {
            "ok": True,
            "id": rec["id"],
            "title": rec["title"],
            "spec": text[:MAX_SPEC_REPLY],
            "truncated": len(text) > MAX_SPEC_REPLY,
        }

    def add(name: str, desc: str, props: dict[str, Any], required: list[str], fn: Handler) -> None:
        registry.register(Tool(name, desc, {"type": "object", "properties": props, "required": required}, _guarded(fn)))

    add(
        "workshop_open",
        "Open (enter) a workshop, the work table where objects no pack covers are built from a part tree. "
        "Without id a NEW workshop is created. id may be a workshop id, deck id or title. Returns {id, params}.",
        {"id": {"type": "string"}, "title": {"type": "string", "description": "name of a new workshop"}},
        [],
        open_,
    )
    add(
        "workshop_build",
        BUILD_DESCRIPTION,
        {"spec": {"type": "object", "description": "the part tree object described above"}},
        ["spec"],
        build,
    )
    add(
        "workshop_param",
        "Set one parameter (slider) of the built object; the value is clamped to its range and redrawn at once.",
        {"name": NAME, "value": {"type": "number"}},
        ["name", "value"],
        param,
    )
    add("workshop_undo", "Undo the last build or parameter change of the open workshop.", {}, [], undo)
    add("workshop_redo", "Redo what workshop_undo took back.", {}, [], redo)
    add(
        "workshop_close",
        "Leave the workshop and return the camera to the desk; the workshop stays on the deck.",
        {},
        [],
        close,
    )
    add(
        "workshop_view_source",
        "The current part tree (spec JSON) of the open workshop, to read it before changing it.",
        {},
        [],
        view_source,
    )
    register_look_tool(registry, session, lambda: pinned_model("agent"))
    register_sources_tool(add, session)
    return session
