# backend/app/model3d/tools_edit.py
"""model_* tools that create and edit models. Errors are returned as {error}."""

from collections.abc import Awaitable, Callable
from typing import Any

from app.model3d.bounds import model_bounds
from app.model3d.changes import edit_fields, remove_part
from app.model3d.compile import root_id
from app.model3d.model import LAYER_DEFAULT, Model, ModelError, Part
from app.model3d.session import ModelSession
from app.model3d.store import norm_id
from app.voice.tools import Tool, ToolRegistry

Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
STR = {"type": "string"}
M = {"type": "string", "description": "model id (case and punctuation are normalised); default is the last used model"}
FRAME = {"type": "boolean", "description": "false keeps the camera where it is; by default the camera frames a new or much larger/smaller model"}


def guarded(fn: Handler) -> Handler:
    async def run(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return await fn(args)
        except ModelError as e:
            return {"error": str(e)}
        except (TypeError, KeyError, ValueError) as e:
            return {"error": f"bad arguments: {e}"}
    return run


def add_tool(reg: ToolRegistry, name: str, desc: str, props: dict[str, Any], required: list[str], fn: Handler, **kw: Any) -> None:
    reg.register(Tool(name, desc, {"type": "object", "properties": props, "required": required}, guarded(fn), **kw))


def register_edit_tools(reg: ToolRegistry, s: ModelSession) -> None:
    async def create(a: dict[str, Any]) -> dict[str, Any]:
        mid = norm_id(a["id"])
        if s.store.exists(mid):
            s.current = mid
            return {"error": f"model '{mid}' exists; use model_edit_part / model_add_part to change it or model_clear to delete it", "model": mid}
        model = s.store.create(mid, a.get("units", "mm"))
        await s.redraw(model)
        note = {} if mid == a["id"] else {"note": f"id normalised from '{a['id']}'"}
        return {"ok": True, "model": model.id, "units": model.units, **note}

    async def add_part(a: dict[str, Any]) -> dict[str, Any]:
        part = Part.from_dict(a["part"])
        def change(m: Model) -> None:
            if part.id in m.parts:
                raise ModelError(f"part '{part.id}' already exists; use model_edit_part")
            m.parts[part.id] = part
        await s.mutate(a, change)
        return {"ok": True, "part": part.id}

    async def edit_part(a: dict[str, Any]) -> dict[str, Any]:
        def change(m: Model) -> None:
            if a["id"] not in m.parts:
                raise ModelError(f"unknown part '{a['id']}'")
            m.parts[a["id"]] = edit_fields(m.parts[a["id"]], a["props"])
        await s.mutate(a, change)
        return {"ok": True, "part": a["id"]}

    async def remove(a: dict[str, Any]) -> dict[str, Any]:
        gone = await s.mutate(a, lambda m: remove_part(m, a["id"]))
        return {"ok": True, "removed": gone}

    async def group(a: dict[str, Any]) -> dict[str, Any]:
        def change(m: Model) -> None:
            if a["id"] in m.parts:
                raise ModelError(f"part '{a['id']}' already exists")
            first = m.parts.get(a["parts"][0]) if a["parts"] else None
            m.parts[a["id"]] = Part(a["id"], "group", a.get("name", ""), first.parent if first else None)
            for pid in a["parts"]:
                if pid not in m.parts:
                    raise ModelError(f"unknown part '{pid}'")
                m.parts[pid].parent = a["id"]
        await s.mutate(a, change)
        return {"ok": True, "group": a["id"], "members": a["parts"]}

    async def layer_set(a: dict[str, Any]) -> dict[str, Any]:
        def change(m: Model) -> None:
            lay = m.layers.setdefault(a["layer"], dict(LAYER_DEFAULT))
            lay.update({k: a[k] for k in LAYER_DEFAULT if k in a})
        await s.mutate(a, change)
        return {"ok": True, "layer": a["layer"]}

    async def undo_redo(a: dict[str, Any], step: Callable[[str], Model]) -> dict[str, Any]:
        before = model_bounds(s.store.load(s.pick(a)))
        model = step(s.pick(a))
        await s.redraw(model, a, before)
        return {"ok": True, "parts": len(model.parts), "history": s.store.history(model.id)}

    async def snapshot(a: dict[str, Any]) -> dict[str, Any]:
        s.store.snapshot(s.pick(a), a["name"])
        return {"ok": True, "name": a["name"]}

    async def restore(a: dict[str, Any]) -> dict[str, Any]:
        before = model_bounds(s.store.load(s.pick(a)))
        model = s.store.restore(s.pick(a), a["name"])
        await s.redraw(model, a, before)
        return {"ok": True, "parts": len(model.parts)}

    async def clear(a: dict[str, Any]) -> dict[str, Any]:
        mid = s.pick(a)
        s.store.delete(mid)
        s.current = None
        await s.push([{"op": "del", "id": root_id(Model(mid))}])
        return {"ok": True, "deleted": mid}

    async def listing(a: dict[str, Any]) -> dict[str, Any]:
        details = []
        for mid in s.store.list():
            m = s.store.load(mid)
            details.append({"id": mid, "units": m.units, "parts": len(m.parts), "layers": sorted({p.layer for p in m.parts.values()})})
        return {"models": s.store.list(), "details": details, "current": s.current}

    pj = {"type": "object", "description": "Part: {id, kind (box|cylinder|extrude|polyline|label|image|gltf|group|...), name?, parent?, pos?, rot?, scale?, color?, opacity?, layer?, tags?, props? (free metadata), geom? (kind props such as pts/text/url), visible?}. For unit primitives (box, cylinder) scale is the size in model units."}
    add_tool(reg, "model_create", "Create an empty parametric model (assembly of parts). units default mm; ids are lower-cased (PCB Model -> pcb_model) and an existing id returns an error. For a PCB, enclosure or building prefer pack_generate, which creates the model and all parts in one call.",
             {"id": STR, "units": {"type": "string", "description": "mm (default), cm, m, in"}}, ["id"], create)
    add_tool(reg, "model_add_part", "Add one part to a model; it is persisted and drawn at once.", {"model": M, "part": pj, "frame": FRAME}, ["part"], add_part)
    add_tool(reg, "model_edit_part", "Change fields of a part; props and geom merge key-wise (null deletes a key).", {"model": M, "id": STR, "props": {"type": "object"}, "frame": FRAME}, ["id", "props"], edit_part)
    add_tool(reg, "model_remove_part", "Remove a part and its children.", {"model": M, "id": STR}, ["id"], remove)
    add_tool(reg, "model_group", "Group existing parts under a new group part.", {"model": M, "id": STR, "parts": {"type": "array", "items": STR}, "name": STR}, ["id", "parts"], group)
    add_tool(reg, "model_layer_set", "Set layer visible/opacity/color/z_index (z_index orders layers in an exploded view).",
             {"model": M, "layer": STR, "visible": {"type": "boolean"}, "opacity": {"type": "number"}, "color": STR, "z_index": {"type": "number"}, "frame": FRAME}, ["layer"], layer_set)
    add_tool(reg, "model_undo", "Undo the last model change.", {"model": M}, [], lambda a: undo_redo(a, s.store.undo))
    add_tool(reg, "model_redo", "Redo an undone model change.", {"model": M}, [], lambda a: undo_redo(a, s.store.redo))
    add_tool(reg, "model_snapshot", "Save the model state under a name; model_restore returns to it.", {"model": M, "name": STR}, ["name"], snapshot)
    add_tool(reg, "model_restore", "Restore a named snapshot (undoable).", {"model": M, "name": STR}, ["name"], restore)
    add_tool(reg, "model_list", "List stored models with id, units, part count and layers.", {}, [], listing)
    add_tool(reg, "model_clear", "Delete a model from disk and the scene. Destructive.", {"model": M}, [], clear,
             risky=True, confirm_summary=lambda a: f"Delete model '{a.get('model') or 'current'}' permanently")
