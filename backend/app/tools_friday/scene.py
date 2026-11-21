# backend/app/tools_friday/scene.py
"""Scene tools: edit and inspect the 3D scene the browser shows."""

from typing import Any

from app.scene_schema import ANIM_TYPES, COMMON, KIND_PROPS, OP_FIELDS, SceneError
from app.tools_friday.ctx import Ctx
from app.voice.tools import Tool, ToolRegistry

_VEC3 = {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}


def scene_apply_description() -> str:
    """Tool description generated from scene_schema, so kinds, props and ops cannot drift."""
    kinds = "; ".join(f"{k}({','.join(sorted(p))})" if p else k for k, p in KIND_PROPS.items())
    ops = ", ".join(f"{o}({','.join(sorted(f - {'op'}))})" if f - {"op"} else o for o, f in OP_FIELDS.items())
    return (
        "Draw or change the 3D scene. Use it whenever the user wants something shown, built, moved, "
        "recolored or removed in 3D. Pass a list of ops applied atomically: if any op is invalid, "
        "nothing changes and an error names the bad field - fix it and call again. "
        f"Ops: {ops}. add takes obj {{id,kind,...props}}; the same id replaces. "
        f"Obj kinds (kind-specific props in brackets): {kinds}. "
        f"Common props: {','.join(sorted(COMMON - {'id', 'kind'}))}. "
        "pos/rot/from/to are [x,y,z]; scale is a number or [x,y,z]; color is a CSS color; parent is an id. "
        f"anim is {{type: {'|'.join(sorted(ANIM_TYPES))}, speed?, axis?, amp?}} or a list of those. "
        "Call scene_get first when editing existing objects so ids are correct."
    )


def register_scene_tools(registry: ToolRegistry, ctx: Ctx) -> None:
    async def scene_apply(args: dict[str, Any]) -> dict[str, Any]:
        ops = args.get("ops")
        if not isinstance(ops, list) or not ops:
            return {"error": "ops must be a non-empty list of op objects"}
        return await _apply(ctx, ops)

    async def scene_get(args: dict[str, Any]) -> dict[str, Any]:
        return {"scene": ctx.scene.describe()}

    async def scene_clear(args: dict[str, Any]) -> dict[str, Any]:
        return await _apply(ctx, [{"op": "clear"}])

    async def scene_camera(args: dict[str, Any]) -> dict[str, Any]:
        op: dict[str, Any] = {"op": "camera", "pos": args.get("pos")}
        if args.get("look") is not None:
            op["look"] = args["look"]
        return await _apply(ctx, [op])

    async def scene_explode(args: dict[str, Any]) -> dict[str, Any]:
        return await _apply(ctx, [{"op": "explode", "factor": args.get("factor")}])

    async def selected_objects(args: dict[str, Any]) -> dict[str, Any]:
        chosen = set(ctx.scene.selected)
        return {"ids": list(ctx.scene.selected), "objects": [o for o in ctx.scene.objects() if o["id"] in chosen]}

    registry.register(Tool(
        "scene_apply", scene_apply_description(),
        {
            "type": "object",
            "properties": {"ops": {"type": "array", "items": {"type": "object"}, "description": "Op objects, e.g. {op:'add',obj:{id:'a',kind:'box',pos:[0,1,0],color:'#f80'}}"}},
            "required": ["ops"],
        },
        scene_apply,
    ))
    registry.register(Tool(
        "scene_get",
        "Read the current 3D scene as a compact text tree (ids, kinds, positions, colors) incl. the "
        "selected ids (marked *). Use before editing existing objects or when asked what is in the scene.",
        {"type": "object", "properties": {}},
        scene_get,
    ))
    registry.register(Tool(
        "scene_clear", "Remove every object from the 3D scene. Use when the user wants to start over.",
        {"type": "object", "properties": {}}, scene_clear,
    ))
    registry.register(Tool(
        "scene_camera",
        "Move the 3D camera to pos, looking at look (default origin). Use for 'zoom in', 'show from above', 'look at X'.",
        {"type": "object", "properties": {"pos": {**_VEC3, "description": "[x,y,z] camera position"}, "look": {**_VEC3, "description": "[x,y,z] target, default [0,0,0]"}}, "required": ["pos"]},
        scene_camera,
    ))
    registry.register(Tool(
        "scene_explode",
        "Exploded view: move parts apart. factor 0 restores, 1 is a normal explosion. Use for 'take it apart' / 'put it back'.",
        {"type": "object", "properties": {"factor": {"type": "number"}}, "required": ["factor"]},
        scene_explode,
    ))
    registry.register(Tool(
        "selected_objects",
        "Return the objects the user clicked in the 3D view. Use to resolve 'this', 'that one', 'make it bigger'.",
        {"type": "object", "properties": {}}, selected_objects,
    ))


async def _apply(ctx: Ctx, ops: list) -> dict[str, Any]:
    try:
        ctx.scene.apply(ops)
    except SceneError as e:
        return {"error": str(e)}
    await ctx.emit({"t": "scene", "ops": ops})
    return {"ok": True, "objects": len(ctx.scene.objects())}
