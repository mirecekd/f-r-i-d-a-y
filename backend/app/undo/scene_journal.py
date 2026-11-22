# backend/app/undo/scene_journal.py
"""Records what a scene-editing tool call changed, as before/after object states, and builds the ops that move between them."""

import copy
from typing import Any

from app.scene import SceneStore

Objects = dict[str, dict[str, Any]]
MOVE_PROPS = ("pos", "rot", "scale", "from", "to")


def snapshot(scene: SceneStore) -> Objects:
    return {o["id"]: dict(o) for o in scene.objects()}  # apply() replaces objects, never edits them in place


def changed_ids(before: Objects, after: Objects) -> list[str]:
    """Ids whose object was added, removed or edited, in a stable order (after first, then removed ones)."""
    ids = [i for i in after if before.get(i) != after[i]]
    return ids + [i for i in before if i not in after]


def transition(src: Objects, dst: Objects, ids: list[str]) -> list[dict[str, Any]]:
    """Ops that turn the `ids` from their `src` state into their `dst` state (deletes first, then adds in dst order)."""
    wanted = set(ids)
    ops: list[dict[str, Any]] = [{"op": "del", "id": i} for i in ids if i not in dst and i in src]
    ops += [{"op": "add", "obj": copy.deepcopy(o)} for i, o in dst.items() if i in wanted]
    return ops


def _noun(n: int) -> str:
    return "1 object" if n == 1 else f"{n} objects"


def describe(before: Objects, after: Objects, ids: list[str]) -> str:
    """Plain words for one change set, e.g. 'moved wall_1', 'added 3 objects', 'cleared the scene'."""
    added = [i for i in ids if i not in before]
    removed = [i for i in ids if i not in after]
    edited = [i for i in ids if i in before and i in after]
    if not after and removed:
        return "cleared the scene"
    moved = [i for i in edited if any(before[i].get(p) != after[i].get(p) for p in MOVE_PROPS)]
    parts: list[str] = []
    for verb, group in (("added", added), ("removed", removed), ("moved", moved), ("changed", [i for i in edited if i not in moved])):
        if group:
            parts.append(f"{verb} {group[0]}" if len(group) == 1 else f"{verb} {_noun(len(group))}")
    return " and ".join(parts) or "a scene change"
