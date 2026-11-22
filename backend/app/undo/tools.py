# backend/app/undo/tools.py
"""`undo` / `redo` voice tools and the {t:'undo'|'redo'} message: scene journal plus delegation to model3d and the workshop."""

from dataclasses import replace
from typing import Any

from app.scene_schema import SceneError
from app.tools_friday.ctx import Ctx
from app.undo.scene_journal import Objects, changed_ids, describe, snapshot, transition
from app.undo.stack import CAP, UndoEntry, UndoStack
from app.voice.tools import Handler, Tool, ToolRegistry

MODEL_CHANGES = {
    "model_add_part", "model_edit_part", "model_remove_part", "model_group", "model_layer_set",
    "model_restore", "model_annotate", "model_accept", "pack_generate",
}
WORKSHOP_CHANGES = {"workshop_build", "workshop_param"}
OWN_HISTORY_PREFIXES = ("model_", "pack_", "workshop_")  # these keep their own history; the scene journal skips them
UNDO_DESCRIPTION = (
    "Undo the last action, whatever made it: a scene edit, an entity move, a link, a deck placement, a model change "
    "or a workshop change. Say what was undone. steps (default 1) undoes several actions. Approval-gated destructive "
    "actions (deck_forget, deleting files, model_clear) are never journaled and cannot be undone this way."
)


class UndoService:
    """Per connection. Build it after every other tool is registered: it wraps their handlers and adds undo / redo."""

    def __init__(self, registry: ToolRegistry, ctx: Ctx) -> None:
        self.registry, self.ctx = registry, ctx
        self.stack = UndoStack()
        self.last_domain = "scene"  # scene | model | workshop: who made the newest undoable action
        for name, tool in list(registry.tools.items()):
            registry.tools[name] = replace(tool, handler=self._wrap(tool))
        registry.register(Tool("undo", UNDO_DESCRIPTION, {"type": "object", "properties": {"steps": {"type": "integer", "description": "how many actions to undo, default 1"}}}, self._undo_tool))
        registry.register(Tool("redo", "Redo what was just undone (the opposite of undo).", {"type": "object", "properties": {}}, self._redo_tool))

    def _wrap(self, tool: Tool) -> Handler:
        name = tool.name
        if tool.risky:
            return tool.handler  # approval-gated destructive tools are never journaled
        if name in MODEL_CHANGES or name in WORKSHOP_CHANGES:
            domain = "model" if name in MODEL_CHANGES else "workshop"

            async def own_history(args: dict[str, Any]) -> dict[str, Any]:
                result = await tool.handler(args)
                if "error" not in result:
                    self.last_domain = domain
                return result

            return own_history
        if name.startswith(OWN_HISTORY_PREFIXES) or name in ("undo", "redo"):
            return tool.handler

        async def journaled(args: dict[str, Any]) -> dict[str, Any]:
            before = snapshot(self.ctx.scene)
            try:
                return await tool.handler(args)
            finally:
                self._record(before, snapshot(self.ctx.scene))

        return journaled

    def _record(self, before: Objects, after: Objects) -> None:
        ids = changed_ids(before, after)
        if not ids:
            return

        async def undo() -> None:
            await self._apply(transition(after, before, ids))

        async def redo() -> None:
            await self._apply(transition(before, after, ids))

        self.stack.push(UndoEntry(describe(before, after, ids), undo, redo))
        self.last_domain = "scene"

    async def _apply(self, ops: list[dict[str, Any]]) -> None:
        self.ctx.scene.apply(ops)
        await self.ctx.emit({"t": "scene", "ops": ops})

    async def _delegate(self, tool_name: str) -> bool:
        """Run the model or workshop own undo / redo tool; False when it has nothing to do."""
        tool = self.registry.tools.get(tool_name)
        if tool is None:
            return False
        result = await tool.handler({})
        return "error" not in result and bool(result)

    async def run(self, redo: bool, steps: int = 1) -> dict[str, Any]:
        verb, past = ("redo", "Redone") if redo else ("undo", "Undone")
        done: list[str] = []
        for _ in range(max(1, min(steps, CAP))):
            try:
                label = await self._one(redo)
            except SceneError as e:
                return {"error": f"Cannot {verb}: the scene no longer accepts it ({e})."}
            if label is None:
                break
            done.append(label)
        if not done:
            return {"error": f"Nothing to {verb}."}
        return {"ok": True, "message": f"{past}: {'; '.join(done)}", "steps": len(done)}

    async def _one(self, redo: bool) -> str | None:
        """One step: the domain of the newest action first, then the scene journal, then the other domains' own history."""
        order = ["model", "workshop"] if self.last_domain == "model" else ["workshop", "model"]
        first = [self.last_domain] if self.last_domain in order else []
        for what in first:
            if await self._delegate(f"{what}_{'redo' if redo else 'undo'}"):
                return f"the last {what} change"
        entry = await (self.stack.redo if redo else self.stack.undo)()
        if entry:
            return entry.label
        for what in (w for w in order if w not in first):
            if await self._delegate(f"{what}_{'redo' if redo else 'undo'}"):
                return f"the last {what} change"
        return None

    async def _undo_tool(self, args: dict[str, Any]) -> dict[str, Any]:
        steps = args.get("steps")
        return await self.run(False, steps if isinstance(steps, int) else 1)

    async def _redo_tool(self, args: dict[str, Any]) -> dict[str, Any]:
        return await self.run(True)

    async def on_message(self, msg: dict[str, Any]) -> None:
        """Browser {t:'undo'|'redo', steps?}: the outcome comes back as a `notice`."""
        steps = msg.get("steps")
        result = await self.run(msg.get("t") == "redo", steps if isinstance(steps, int) else 1)
        await self.ctx.emit({"t": "notice", "text": result.get("message") or result["error"]})
