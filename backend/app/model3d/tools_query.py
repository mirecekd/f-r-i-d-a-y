# backend/app/model3d/tools_query.py
"""model_* tools that read, explode, annotate and propose; plus pack tools. Errors are returned as {error}."""

from typing import Any

from app.model3d.bounds import model_bounds
from app.model3d.compile import compile_model
from app.model3d.explode import explode
from app.model3d.measure import describe_model, measure
from app.model3d.model import Model, ModelError, Part
from app.model3d.packs import catalog, filled_spec, get_pack, list_packs, pack_info
from app.model3d.session import ModelSession
from app.model3d.store import norm_id
from app.model3d.tools_edit import FRAME, STR, M, add_tool
from app.voice.tools import ToolRegistry


def register_query_tools(reg: ToolRegistry, s: ModelSession) -> None:
    async def get(a: dict[str, Any]) -> dict[str, Any]:
        return {"model": describe_model(s.load(a))}

    async def meas(a: dict[str, Any]) -> dict[str, Any]:
        return measure(s.load(a), a["a"], a["b"])

    async def annotate(a: dict[str, Any]) -> dict[str, Any]:
        def change(m: Model) -> str:
            if a["part"] not in m.parts:
                raise ModelError(f"unknown part '{a['part']}'")
            n = sum(1 for p in m.parts.values() if "annotation" in p.tags) + 1
            while f"note{n}" in m.parts:
                n += 1
            host = m.parts[a["part"]]
            m.parts[f"note{n}"] = Part(f"note{n}", "label", parent=host.id, layer=host.layer, tags=["annotation"],
                                       geom={"text": a["text"], "size": a.get("size", 1.0)})
            return f"note{n}"
        return {"ok": True, "annotation": await s.mutate(a, change)}

    async def do_explode(a: dict[str, Any]) -> dict[str, Any]:
        model = s.load(a)
        ops = explode(model, a["factor"], a.get("by", "layer"), a.get("axis", "y"), a.get("spacing"))
        prefix = f"m:{model.id}:"
        moved = {o["id"][len(prefix):]: o["props"]["pos"] for o in ops}
        ops += s.framing(a, model, None, model_bounds(model, moved))
        await s.push(ops)
        return {"ok": True, "moved": len(moved), "factor": a["factor"]}

    async def propose(a: dict[str, Any]) -> dict[str, Any]:
        prop = s.book.propose(s.load(a), a["changes"])
        await s.push(prop.ghost_ops)
        return {"ok": True, "proposal": prop.id, "diff": prop.summary,
                "hint": "ghost shown in the scene; call model_accept or model_reject"}

    async def accept(a: dict[str, Any]) -> dict[str, Any]:
        before = model_bounds(s.store.load(s.book.get(a["proposal"]).model_id))
        model, removal = s.book.accept(a["proposal"], s.store)
        s.current = model.id
        await s.push([*removal, *compile_model(model), *s.framing(a, model, before, model_bounds(model))])
        return {"ok": True, "parts": len(model.parts)}

    async def reject(a: dict[str, Any]) -> dict[str, Any]:
        await s.push(s.book.reject(a["proposal"]))
        return {"ok": True}

    async def packs(a: dict[str, Any]) -> dict[str, Any]:
        return {"packs": {n: {"example_spec": pack_info(n).example, "units": pack_info(n).units} for n in list_packs()}}

    async def generate(a: dict[str, Any]) -> dict[str, Any]:
        """Run the pack with defaults filled in; build (or replace) a model with the parts unless dry_run."""
        fn = get_pack(a["pack"])
        if fn is None:
            raise ModelError(f"unknown pack '{a['pack']}'; known: {list_packs()}")
        info = pack_info(a["pack"])
        spec = filled_spec(a["pack"], a.get("spec"))
        mid = norm_id(a.get("model") or a["pack"])
        if a["pack"] == "enclosure":
            spec.setdefault("model_id", mid)
        parts = fn(spec)
        if a.get("dry_run"):
            return {"parts": parts, "spec_used": spec}
        model = Model.from_dict({"id": mid, "units": info.units, "parts": parts, "layers": info.layers(parts) if info.layers else {}})
        if s.store.exists(mid):
            s.store.commit(s.store.load(mid), model)
        else:
            s.store.save(model)
        await s.redraw(model, a)
        by_layer: dict[str, int] = {}
        for p in model.parts.values():
            by_layer[p.layer] = by_layer.get(p.layer, 0) + 1
        return {"ok": True, "model": mid, "parts": len(model.parts), "layers": by_layer, "spec_used": spec,
                "hint": "model is drawn and framed; tell the user what was made and offer to adjust size, components or an exploded view"}

    add_tool(reg, "model_get", "Read a model as a compact text tree (ids, kinds, layers, positions, props). Use before editing or answering questions about it.", {"model": M}, [], get)
    add_tool(reg, "model_measure", "Distance and delta between two part origins, in model units.", {"model": M, "a": STR, "b": STR}, ["a", "b"], meas)
    add_tool(reg, "model_annotate", "Attach a text label to a part.", {"model": M, "part": STR, "text": STR, "size": {"type": "number"}}, ["part", "text"], annotate)
    add_tool(reg, "model_explode", "Exploded view. by=layer (stack layers by z_index)|group (each top-level part)|radial (away from centroid); axis x|y|z; factor 0 restores animated.",
             {"model": M, "factor": {"type": "number"}, "by": {"type": "string", "enum": ["layer", "group", "radial"]},
              "axis": {"type": "string", "enum": ["x", "y", "z"]}, "spacing": {"type": "number", "description": "model units between steps"}, "frame": FRAME}, ["factor"], do_explode)
    add_tool(reg, "model_propose", "Stage changes as a translucent ghost overlay without modifying the model. changes: [{op:'add'|'edit'|'remove', part:{...}|id, props}]. Returns a proposal id and a diff; then ask the user and call model_accept or model_reject.",
             {"model": M, "changes": {"type": "array", "items": {"type": "object"}}}, ["changes"], propose)
    add_tool(reg, "model_accept", "Apply a proposal to the model (undoable) and remove its ghost.", {"proposal": STR}, ["proposal"], accept)
    add_tool(reg, "model_reject", "Discard a proposal and remove its ghost.", {"proposal": STR}, ["proposal"], reject)
    add_tool(reg, "pack_list", "List domain packs (pcb, enclosure, building) with an example spec each.", {}, [], packs)
    add_tool(reg, "pack_generate",
             "Generate a complete model from a domain pack in ONE call: creates (or replaces) the model, adds all parts and layers, draws it and frames the camera. "
             "Use at once for a PCB, enclosure or building request; spec is optional and missing fields get sensible defaults (never ask for dimensions first, refine afterwards with model_edit_part or another pack_generate). "
             "Packs and example specs: " + catalog() + ". Sizes: pcb mm, enclosure mm, building m. Pass model to name the model (default: the pack name). dry_run returns part dicts only.",
             {"pack": {"type": "string", "enum": list_packs()}, "spec": {"type": "object"}, "model": STR, "dry_run": {"type": "boolean"}, "frame": FRAME}, ["pack"], generate)
