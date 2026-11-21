# backend/app/workshop/session.py
"""Per-connection workshop state: enter / leave, build, parameter changes, undo and redo of the current workshop."""

import copy
from typing import Any

from app.model3d.bounds import changed_substantially
from app.model3d.model import ModelError
from app.scene_schema import SceneError
from app.tools_friday.ctx import Ctx
from app.workshop import deck_hooks, sources, store
from app.workshop.draw import Drawn, check_spec_size, draw
from app.workshop.look import SnapshotBroker
from app.workshop.spec import SpecError, with_params

WORKSHOP_ERRORS = (store.WorkshopError, SpecError, ModelError, SceneError)


class WorkshopSession:
    def __init__(self, ctx: Ctx) -> None:
        self.ctx, self.emit = ctx, ctx.emit
        self.current: dict[str, Any] | None = None
        self._bounds: Any = None  # bounds of the model on screen, to decide when the camera reframes
        self._last_param: str | None = None  # consecutive moves of one slider make a single undo step
        self._pending: dict[str, float] = {}
        self._busy = False
        self.broker = SnapshotBroker()
        deck_hooks.attach(ctx, self)

    def close(self) -> None:
        self.broker.cancel_all()
        deck_hooks.detach(self.ctx)

    def require(self) -> dict[str, Any]:
        if self.current is None:
            raise store.WorkshopError("no workshop is open; call workshop_open first")
        return self.current

    async def _push(self, drawn: Drawn, frame: bool) -> None:
        ops = drawn.ops + ([drawn.camera] if frame else [])
        self.ctx.scene.apply(ops)
        await self.emit({"t": "scene", "ops": ops})

    async def _send_params(self, rec: dict[str, Any], drawn: Drawn) -> None:
        await self.emit(
            {"t": "workshop", "op": "params", "id": rec["id"], "params": drawn.params, "notes": drawn.notes}
        )

    def _persist(self, rec: dict[str, Any], drawn: Drawn) -> None:
        rec["values"] = {p["name"]: p["value"] for p in drawn.params}
        store.save(rec)
        deck_hooks.register_item(rec, drawn.parts, len(drawn.params))

    async def open(self, ref: object = None, title: str | None = None) -> dict[str, Any]:
        """Enter the workshop `ref` (workshop id, deck id, tile id or title), or create a new one when `ref` is empty."""
        if ref in (None, ""):
            rec = store.create(title)
        else:
            wid = deck_hooks.resolve(ref)
            if wid is None:
                raise store.WorkshopError(f"unknown workshop {str(ref)[:60]!r}; open the Deck to see the workshops")
            rec = store.load(wid)
        notes: list[str] = sources.drop_dead(rec)
        try:
            drawn = draw(rec)
        except (SpecError, ModelError) as e:
            drawn = draw({**rec, "spec": None})
            notes.append(f"the stored spec cannot be drawn ({e}); build it again")
        drawn.notes = notes + drawn.notes
        await self._push(drawn, frame=False)
        self.ctx.scene.apply(
            [drawn.camera]
        )  # the browser glides from the `enter` message, the server only records the pose
        self.current, self._bounds, self._last_param = rec, drawn.bounds, None
        deck_hooks.register_item(rec, drawn.parts, len(drawn.params))
        await deck_hooks.put_on_desk(self.ctx, rec)
        await self.emit(
            {
                "t": "workshop",
                "op": "enter",
                "id": rec["id"],
                "title": rec["title"],
                "origin": list(store.origin_of(rec["origin_n"])),
                "camera": {"pos": drawn.camera["pos"], "look": drawn.camera["look"]},
                "home": None,  # None: the browser keeps the pose it had when the user entered
                "params": drawn.params,
                "sources": sources.tiles(rec),
                "notes": drawn.notes,
            }
        )
        await sources.place(self.ctx, rec)
        return {"ok": True, "id": rec["id"], "title": rec["title"], "params": drawn.params, "notes": drawn.notes}

    async def leave(self) -> dict[str, Any]:
        """Glide back to the desk; the workshop objects stay in the scene."""
        rec = self.require()
        self.current = None
        await self.emit({"t": "workshop", "op": "leave", "id": rec["id"], "camera": None})
        return {"ok": True, "id": rec["id"]}

    async def build(self, spec: object) -> dict[str, Any]:
        """Replace the whole part tree: validate, draw, then store the old spec as one undo step."""
        rec = self.require()
        data = check_spec_size(spec)
        drawn = draw({**rec, "spec": data})
        await self._push(drawn, changed_substantially(self._bounds, drawn.bounds))
        rec["history"].append(rec["spec"])
        rec["redo"], rec["spec"], self._bounds, self._last_param = [], copy.deepcopy(data), drawn.bounds, None
        name = data.get("name")
        if rec["title"] == store.DEFAULT_TITLE and isinstance(name, str) and name.strip():
            rec["title"] = name.strip()[:120]
            await deck_hooks.put_on_desk(self.ctx, rec, only_if_present=True)
        self._persist(rec, drawn)
        await self._send_params(rec, drawn)
        return {"ok": True, "id": rec["id"], "parts": drawn.parts, "params": drawn.params, "notes": drawn.notes}

    async def param(self, name: object, value: object) -> dict[str, Any]:
        """Set one parameter. While a change is being drawn only the newest value per name is kept (never a queue)."""
        rec = self.require()
        if not isinstance(name, str) or isinstance(value, bool) or not isinstance(value, (int, float)):
            raise store.WorkshopError("workshop_param needs a parameter name and a number")
        if rec["spec"] is None:
            raise store.WorkshopError("nothing is built yet; call workshop_build first")
        self._pending[name] = float(value)
        if self._busy:
            return {"ok": True, "note": "a change is being drawn; the newest value will be applied"}
        self._busy = True
        try:
            result: dict[str, Any] = {"ok": True}
            while self._pending:
                pname, pvalue = self._pending.popitem()
                result = await self._apply_param(rec, pname, pvalue)
            return result
        finally:
            self._busy = False
            self._pending.clear()

    async def _apply_param(self, rec: dict[str, Any], name: str, value: float) -> dict[str, Any]:
        spec = with_params(rec["spec"], {name: value})
        drawn = draw({**rec, "spec": spec})
        await self._push(drawn, frame=False)
        if self._last_param != name:
            rec["history"].append(rec["spec"])
            rec["redo"] = []
        rec["spec"], self._last_param, self._bounds = spec, name, drawn.bounds
        self._persist(rec, drawn)
        await self._send_params(rec, drawn)
        return {"ok": True, "params": drawn.params, "notes": drawn.notes}

    async def step(self, undo: bool) -> dict[str, Any]:
        rec = self.require()
        src, dst = ("history", "redo") if undo else ("redo", "history")
        if not rec[src]:
            raise store.WorkshopError(f"nothing to {'undo' if undo else 'redo'}")
        target = rec[src][-1]
        drawn = draw({**rec, "spec": target})
        await self._push(drawn, changed_substantially(self._bounds, drawn.bounds))
        rec[src].pop()
        rec[dst].append(rec["spec"])
        rec["spec"], self._bounds, self._last_param = target, drawn.bounds, None
        self._persist(rec, drawn)
        await self._send_params(rec, drawn)
        return {"ok": True, "parts": drawn.parts, "params": drawn.params, "notes": drawn.notes}
