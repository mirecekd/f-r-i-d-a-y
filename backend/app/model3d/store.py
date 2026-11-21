# backend/app/model3d/store.py
"""Model persistence under <FRIDAY_DATA_DIR>/models with an undo/redo snapshot history (cap 50)."""

import json
import os
import re
from pathlib import Path

from app.model3d.model import ID_RE, Model, ModelError

MAX_HISTORY = 50


def models_dir() -> Path:
    return Path(os.getenv("FRIDAY_DATA_DIR", "/srv/data")) / "models"


def norm_id(model_id: str) -> str:
    """Canonical model id: lower case, runs of other characters become one underscore ('PCB Model' -> 'pcb_model')."""
    if not isinstance(model_id, str):
        raise ModelError(f"model id {model_id!r} must be a string")
    out = re.sub(r"[^a-z0-9]+", "_", model_id.lower()).strip("_")[:64]
    if not ID_RE.match(out):
        raise ModelError(f"model id {model_id!r} has no letters or digits")
    return out


def _write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, path)


class ModelStore:
    """Live models by id. Every `commit` pushes the previous state on the undo stack and saves to disk."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or models_dir()
        self._undo: dict[str, list[dict]] = {}
        self._redo: dict[str, list[dict]] = {}
        self._named: dict[str, dict[str, dict]] = {}

    def _path(self, model_id: str) -> Path:
        return self.root / f"{norm_id(model_id)}.json"

    def exists(self, model_id: str) -> bool:
        return self._path(model_id).is_file()

    def create(self, model_id: str, units: str = "mm", scale_to_scene: float | None = None) -> Model:
        from app.model3d.model import UNIT_SCALE
        model_id = norm_id(model_id)
        if self.exists(model_id):
            raise ModelError(f"model '{model_id}' already exists")
        model = Model(model_id, units, scale_to_scene or UNIT_SCALE.get(units, 1.0))
        model.validate()
        self.save(model)
        return model

    def load(self, model_id: str) -> Model:
        path = self._path(model_id)
        if not path.is_file():
            raise ModelError(f"unknown model '{model_id}'; known: {self.list()}")
        return Model.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, model: Model) -> None:
        model.validate()
        _write_atomic(self._path(model.id), model.to_dict())

    def commit(self, before: Model, after: Model) -> None:
        """Persist `after`; `before` becomes the next undo state and the redo stack is dropped."""
        self.save(after)
        stack = self._undo.setdefault(after.id, [])
        stack.append(before.to_dict())
        del stack[:-MAX_HISTORY]
        self._redo[after.id] = []

    def undo(self, model_id: str) -> Model:
        return self._step(norm_id(model_id), self._undo, self._redo, "undo")

    def redo(self, model_id: str) -> Model:
        return self._step(norm_id(model_id), self._redo, self._undo, "redo")

    def _step(self, model_id: str, src: dict, dst: dict, what: str) -> Model:
        stack = src.get(model_id) or []
        if not stack:
            raise ModelError(f"nothing to {what}")
        current = self.load(model_id)
        target = Model.from_dict(stack.pop())
        dst.setdefault(model_id, []).append(current.to_dict())
        self.save(target)
        return target

    def snapshot(self, model_id: str, name: str) -> None:
        model_id = norm_id(model_id)
        if not isinstance(name, str) or not re.match(r"^[\w .\-]{1,64}$", name):
            raise ModelError("snapshot name must be 1-64 chars of letters, digits, space, _ . -")
        self._named.setdefault(model_id, {})[name] = self.load(model_id).to_dict()

    def restore(self, model_id: str, name: str) -> Model:
        model_id = norm_id(model_id)
        snap = self._named.get(model_id, {}).get(name)
        if snap is None:
            raise ModelError(f"unknown snapshot '{name}'; known: {sorted(self._named.get(model_id, {}))}")
        before = self.load(model_id)
        after = Model.from_dict(snap)
        self.commit(before, after)
        return after

    def history(self, model_id: str) -> tuple[int, int]:
        model_id = norm_id(model_id)
        return len(self._undo.get(model_id, [])), len(self._redo.get(model_id, []))

    def list(self) -> list[str]:
        return sorted(p.stem for p in self.root.glob("*.json")) if self.root.is_dir() else []

    def delete(self, model_id: str) -> None:
        model_id = norm_id(model_id)
        self._path(model_id).unlink(missing_ok=True)
        for d in (self._undo, self._redo, self._named):
            d.pop(model_id, None)
