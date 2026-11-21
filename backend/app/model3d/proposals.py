# backend/app/model3d/proposals.py
"""Staged changes shown as a ghost overlay in the scene; the model changes only on accept."""

import itertools
from dataclasses import dataclass
from typing import Any

from app.model3d.bounds import effective_scale
from app.model3d.changes import apply_changes, change_target, check_changes, diff_summary
from app.model3d.compile import part_obj, part_scene_id
from app.model3d.model import Model, ModelError
from app.model3d.store import ModelStore
from app.scene_schema import check_op

GHOST_COLORS = {"add": "#3fdc7a", "edit": "#ffb02e", "remove": "#ff4d4d"}
GHOST_OPACITY = 0.35


def ghost_id(proposal_id: str, part_id: str) -> str:
    return f"ghost:{proposal_id}:{part_id}"


@dataclass
class Proposal:
    id: str
    model_id: str
    changes: list[dict[str, Any]]
    summary: str
    ghost_ops: list[dict[str, Any]]
    ghost_ids: list[str]


def ghost_ops(model: Model, proposal_id: str, changes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Translucent, colour-coded copies of the touched parts; returns (ops, ids to delete on rejection)."""
    after = apply_changes(model, changes)
    kinds: dict[str, str] = {}
    for c in changes:
        kinds[change_target(c)] = c["op"]
    group = f"ghost:{proposal_id}"
    ops: list[dict[str, Any]] = [{"op": "add", "obj": {"id": group, "kind": "group", "scale": effective_scale(model)}}]
    ids = [group]
    for pid, op in kinds.items():
        part = after.parts.get(pid) or model.parts.get(pid)
        if part is None:  # added then removed inside the same proposal
            continue
        if part.parent in kinds and kinds[part.parent] != "remove" and part.parent in after.parts:
            parent = ghost_id(proposal_id, part.parent)
        elif part.parent in model.parts:
            parent = part_scene_id(model, part.parent)
        else:
            parent = group
        style = {"color": GHOST_COLORS[op], "opacity": GHOST_OPACITY}
        ops.append({"op": "add", "obj": part_obj(model, part, ghost_id(proposal_id, pid), parent, style)})
        ids.append(ghost_id(proposal_id, pid))
    for op in ops:
        check_op(op)
    return ops, ids


class ProposalBook:
    """Open proposals of one connection."""

    def __init__(self) -> None:
        self._open: dict[str, Proposal] = {}
        self._seq = itertools.count(1)

    def clear(self) -> list[dict[str, Any]]:
        """Forget every open proposal; returns the ops removing their ghosts."""
        ops = [op for prop in self._open.values() for op in self._removal(prop)]
        self._open.clear()
        return ops

    def get(self, proposal_id: str) -> Proposal:
        if proposal_id not in self._open:
            raise ModelError(f"unknown proposal '{proposal_id}'; open: {sorted(self._open)}")
        return self._open[proposal_id]

    def propose(self, model: Model, changes: list[dict[str, Any]]) -> Proposal:
        """Stage `changes` as a ghost overlay. The model is not modified."""
        check_changes(changes)
        pid = f"p{next(self._seq)}"
        after = apply_changes(model, changes)
        ops, ids = ghost_ops(model, pid, changes)
        prop = Proposal(pid, model.id, changes, diff_summary(model, after), ops, ids)
        self._open[pid] = prop
        return prop

    def accept(self, proposal_id: str, store: ModelStore) -> tuple[Model, list[dict[str, Any]]]:
        """Snapshot, apply the changes to the stored model; return (new model, ops removing the ghost)."""
        prop = self.get(proposal_id)
        before = store.load(prop.model_id)
        after = apply_changes(before, prop.changes)
        store.commit(before, after)
        del self._open[proposal_id]
        return after, self._removal(prop)

    def reject(self, proposal_id: str) -> list[dict[str, Any]]:
        prop = self.get(proposal_id)
        del self._open[proposal_id]
        return self._removal(prop)

    @staticmethod
    def _removal(prop: Proposal) -> list[dict[str, Any]]:
        return [{"op": "del", "id": i} for i in reversed(prop.ghost_ids)]
