# backend/app/model3d/changes.py
"""Apply a list of part changes ({op: add|edit|remove, part|id, props}) to a copy of a Model."""

from typing import Any

from app.model3d.model import Model, ModelError, Part

OPS = ("add", "edit", "remove")


def edit_fields(part: Part, props: dict[str, Any]) -> Part:
    """New Part with `props` merged in; `props` and `geom` merge key-wise, other fields are replaced. id is fixed."""
    if not isinstance(props, dict):
        raise ModelError("props must be an object")
    d = part.to_dict()
    for k, v in props.items():
        if k == "id":
            raise ModelError("a part id cannot be changed; remove and add instead")
        d[k] = {**d[k], **v} if k in ("props", "geom") and isinstance(v, dict) else v
        if k in ("props", "geom") and isinstance(v, dict):
            d[k] = {kk: vv for kk, vv in d[k].items() if vv is not None}
    return Part.from_dict(d)


def remove_part(model: Model, pid: str) -> list[str]:
    """Remove a part and all its descendants from `model`; return the removed ids."""
    if pid not in model.parts:
        raise ModelError(f"unknown part '{pid}'")
    gone = [pid] + [p.id for p in model.descendants(pid)]
    for g in gone:
        del model.parts[g]
    return gone


def check_changes(changes: object) -> list[dict[str, Any]]:
    if not isinstance(changes, list) or not changes:
        raise ModelError("changes must be a non-empty list")
    for c in changes:
        if not isinstance(c, dict) or c.get("op") not in OPS:
            raise ModelError(f"each change needs op in {list(OPS)}")
    return changes


def change_target(c: dict[str, Any]) -> str:
    part = c.get("part")
    pid = c.get("id") or (part.get("id") if isinstance(part, dict) else part)
    if not isinstance(pid, str) or not pid:
        raise ModelError(f"change '{c.get('op')}' needs a part id")
    return pid


def apply_changes(model: Model, changes: list[dict[str, Any]]) -> Model:
    """Return a validated copy of `model` with all changes applied in order; `model` is not modified."""
    out = Model.from_dict(model.to_dict())
    for c in check_changes(changes):
        pid = change_target(c)
        if c["op"] == "add":
            if pid in out.parts:
                raise ModelError(f"part '{pid}' already exists")
            data = c["part"] if isinstance(c.get("part"), dict) else {"id": pid, **(c.get("props") or {})}
            out.parts[pid] = Part.from_dict(data)
        elif c["op"] == "edit":
            if pid not in out.parts:
                raise ModelError(f"unknown part '{pid}'")
            out.parts[pid] = edit_fields(out.parts[pid], c.get("props") or {})
        else:
            remove_part(out, pid)
    out.validate()
    return out


def diff_summary(before: Model, after: Model) -> str:
    """Human-readable diff between two states of one model."""
    lines = []
    for pid, p in after.parts.items():
        old = before.parts.get(pid)
        if old is None:
            lines.append(f"+ add {pid} ({p.kind}) at {p.pos}")
        elif old.to_dict() != p.to_dict():
            a, b = old.to_dict(), p.to_dict()
            lines.append(f"~ edit {pid}: " + ", ".join(f"{k} {a[k]} -> {b[k]}" for k in a if a[k] != b[k]))
    lines += [f"- remove {pid} ({p.kind})" for pid, p in before.parts.items() if pid not in after.parts]
    return "\n".join(lines) or "no changes"
