# backend/app/model3d/visible.py
"""Which parts of a model are shown; shared by compile and bounds."""

from app.model3d.model import Model, Part


def visible_parts(model: Model) -> list[Part]:
    """Parts that are shown (own flag and layer flag, and every ancestor shown), parents before children."""
    out: list[Part] = []
    todo = model.children(None)
    while todo:
        p = todo.pop(0)
        if p.visible and model.layer(p.layer)["visible"]:
            out.append(p)
            todo += model.children(p.id)
    return out
