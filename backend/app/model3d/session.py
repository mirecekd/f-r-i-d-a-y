# backend/app/model3d/session.py
"""Per-connection glue: store + proposals + pushing compiled ops to the scene and the browser."""

from collections.abc import Callable
from typing import Any

from app.model3d.bounds import Bounds, changed_substantially, frame_op, model_bounds
from app.model3d.compile import compile_model
from app.model3d.model import Model, ModelError
from app.model3d.proposals import ProposalBook
from app.model3d.store import ModelStore
from app.scene_schema import SceneError


class ModelSession:
    def __init__(self, ctx: Any, store: ModelStore | None = None) -> None:
        self.ctx = ctx
        self.store = store or ModelStore()
        self.book = ProposalBook()
        self.current: str | None = None

    async def reset_transient(self) -> None:
        """New conversation: drop open proposals (and their ghosts) and the current-model pointer; stored models stay."""
        ops = self.book.clear()
        self.current = None
        if ops:
            await self.push(ops)

    def pick(self, args: dict[str, Any]) -> str:
        mid = args.get("model") or self.current
        if not mid:
            raise ModelError("no model selected; call model_create first or pass 'model'")
        return mid

    def load(self, args: dict[str, Any]) -> Model:
        model = self.store.load(self.pick(args))
        self.current = model.id
        return model

    async def push(self, ops: list[dict[str, Any]]) -> None:
        """Apply ops to the server scene and tell the browser; on SceneError nothing changes."""
        try:
            self.ctx.scene.apply(ops)
        except SceneError as e:
            raise ModelError(f"scene rejected the ops: {e}") from e
        await self.ctx.emit({"t": "scene", "ops": ops})

    @staticmethod
    def framing(args: dict[str, Any], model: Model, before: Bounds | None, after: Bounds | None, force: bool = False) -> list[dict[str, Any]]:
        """One camera op framing `model` when it is new or its size changed a lot (or `force`); none when args has frame=false."""
        if args.get("frame") is False or after is None or not (force or changed_substantially(before, after)):
            return []
        return [frame_op(model, after)]

    async def mutate(self, args: dict[str, Any], change: Callable[[Model], Any], force_frame: bool = False) -> Any:
        """Load a copy, let `change` edit it, validate, persist with undo state and redraw the model."""
        before = self.load(args)
        after = Model.from_dict(before.to_dict())
        result = change(after)
        after.validate()
        ops = compile_model(after) + self.framing(args, after, model_bounds(before), model_bounds(after), force_frame)
        await self.push(ops)
        self.store.commit(before, after)
        return result

    async def redraw(self, model: Model, args: dict[str, Any] | None = None, before: Bounds | None = None) -> None:
        """Draw `model`; with `args` also frame it when it is new (`before` None) or its size changed a lot."""
        self.current = model.id
        extra = self.framing(args, model, before, model_bounds(model)) if args is not None else []
        await self.push(compile_model(model) + extra)
