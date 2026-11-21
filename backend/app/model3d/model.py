# backend/app/model3d/model.py
"""Plain-dataclass assembly model: Part and Model with JSON (de)serialization and validation."""

import re
from dataclasses import dataclass, field, fields
from typing import Any

from app.scene_schema import COMMON, KIND_PROPS, SceneError, check_props

MAX_PARTS = 5000
ID_RE = re.compile(r"^[\w.\-]{1,64}$")
UNIT_SCALE = {"mm": 0.001, "cm": 0.01, "m": 1.0, "in": 0.0254}
LAYER_DEFAULT = {"visible": True, "opacity": 1.0, "color": None, "z_index": 0}


class ModelError(ValueError):
    """A model or part that violates the model rules."""


def _num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) < 1e9


@dataclass
class Part:
    id: str
    kind: str = "group"
    name: str = ""
    parent: str | None = None
    pos: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    rot: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    scale: Any = 1.0  # number or [x, y, z]; for unit primitives this is the size in model units
    color: str | None = None
    opacity: float | None = None
    layer: str = "default"
    tags: list[str] = field(default_factory=list)
    props: dict[str, Any] = field(default_factory=dict)  # free metadata, never sent to the scene
    geom: dict[str, Any] = field(default_factory=dict)  # scene props of the kind (pts, text, url, ...)
    visible: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, d: object) -> "Part":
        if not isinstance(d, dict):
            raise ModelError("part must be an object")
        unknown = set(d) - {f.name for f in fields(cls)}
        if unknown:
            raise ModelError(
                f"unknown part fields {sorted(unknown)}; geometry props go into 'geom', metadata into 'props'"
            )
        if "id" not in d:
            raise ModelError("part needs an id")
        part = cls(**{k: _copy(v) for k, v in d.items()})
        part.check()
        return part

    def check(self) -> None:
        if not isinstance(self.id, str) or not ID_RE.match(self.id):
            raise ModelError(f"part id {self.id!r} must match [A-Za-z0-9_.-]{{1,64}}")
        if self.kind not in KIND_PROPS:
            raise ModelError(f"part {self.id}: unknown kind '{self.kind}'; known: {sorted(KIND_PROPS)}")
        for name in ("pos", "rot"):
            v = getattr(self, name)
            if not (isinstance(v, list) and len(v) == 3 and all(_num(x) for x in v)):
                raise ModelError(f"part {self.id}: {name} must be [x, y, z] numbers")
        s = self.scale
        if not (_num(s) or (isinstance(s, list) and len(s) == 3 and all(_num(x) for x in s))):
            raise ModelError(f"part {self.id}: scale must be a number or [x, y, z]")
        if self.opacity is not None and not (_num(self.opacity) and 0 <= self.opacity <= 1):
            raise ModelError(f"part {self.id}: opacity must be 0..1")
        if (
            not all(isinstance(x, str) for x in (self.name, self.layer))
            or self.color is not None
            and not isinstance(self.color, str)
        ):
            raise ModelError(f"part {self.id}: name, layer and color must be strings")
        if not (isinstance(self.tags, list) and all(isinstance(t, str) for t in self.tags)):
            raise ModelError(f"part {self.id}: tags must be a list of strings")
        if not isinstance(self.props, dict) or not isinstance(self.geom, dict) or not isinstance(self.visible, bool):
            raise ModelError(f"part {self.id}: props and geom must be objects, visible a boolean")
        if set(self.geom) & COMMON:
            raise ModelError(f"part {self.id}: geom holds only kind props, not {sorted(set(self.geom) & COMMON)}")
        try:
            check_props(self.kind, self.geom, allow_identity=False)
        except SceneError as e:
            raise ModelError(f"part {self.id}: geom: {e}") from e


def _copy(v: Any) -> Any:
    return (
        [_copy(x) for x in v]
        if isinstance(v, list)
        else {k: _copy(x) for k, x in v.items()}
        if isinstance(v, dict)
        else v
    )


@dataclass
class Model:
    id: str
    units: str = "mm"
    scale_to_scene: float = 0.001  # true scale; the scene root uses a fitted scale when auto_fit is set
    auto_fit: bool = True
    parts: dict[str, Part] = field(default_factory=dict)
    layers: dict[str, dict[str, Any]] = field(default_factory=dict)
    origin: tuple[float, float, float] = (
        0.0,
        0.0,
        0.0,
    )  # scene position of the root group (a workshop lives far from the desk)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "id": self.id,
            "units": self.units,
            "scale_to_scene": self.scale_to_scene,
            "auto_fit": self.auto_fit,
            "parts": [p.to_dict() for p in self.parts.values()],
            "layers": _copy(self.layers),
        }
        if self.origin != (0.0, 0.0, 0.0):
            d["origin"] = list(self.origin)
        return d

    @classmethod
    def from_dict(cls, d: object) -> "Model":
        if not isinstance(d, dict) or not isinstance(d.get("id"), str):
            raise ModelError("model must be an object with an id")
        units = d.get("units", "mm")
        model = cls(
            d["id"],
            units,
            d.get("scale_to_scene", UNIT_SCALE.get(units, 1.0)),
            bool(d.get("auto_fit", True)),
            {},
            _copy(d.get("layers", {})),
        )
        raw_origin = d.get("origin", [0, 0, 0])
        if not (isinstance(raw_origin, list) and len(raw_origin) == 3 and all(_num(v) for v in raw_origin)):
            raise ModelError("origin must be [x, y, z] numbers")
        model.origin = (float(raw_origin[0]), float(raw_origin[1]), float(raw_origin[2]))
        raw = d.get("parts", [])
        if not isinstance(raw, list):
            raise ModelError("parts must be a list")
        for item in raw:
            part = Part.from_dict(item)
            if part.id in model.parts:
                raise ModelError(f"duplicate part id '{part.id}'")
            model.parts[part.id] = part
        model.validate()
        return model

    def layer(self, name: str) -> dict[str, Any]:
        return {**LAYER_DEFAULT, **self.layers.get(name, {})}

    def children(self, pid: str | None) -> list[Part]:
        return [p for p in self.parts.values() if p.parent == pid]

    def descendants(self, pid: str) -> list[Part]:
        out, todo = [], [pid]
        while todo:
            kids = self.children(todo.pop())
            out += kids
            todo += [k.id for k in kids]
        return out

    def validate(self) -> None:
        if not ID_RE.match(self.id):
            raise ModelError(f"model id {self.id!r} must match [A-Za-z0-9_.-]{{1,64}}")
        if not isinstance(self.units, str) or not _num(self.scale_to_scene) or self.scale_to_scene <= 0:
            raise ModelError("units must be a string and scale_to_scene a positive number")
        if len(self.parts) > MAX_PARTS:
            raise ModelError(f"model would hold {len(self.parts)} parts; the limit is {MAX_PARTS}")
        for pid, p in self.parts.items():
            p.check()
            if p.parent is not None and p.parent not in self.parts:
                raise ModelError(f"part {pid}: parent '{p.parent}' does not exist")
            seen, cur = {pid}, p.parent
            while cur is not None:
                if cur in seen:
                    raise ModelError(f"part {pid}: parent chain forms a cycle")
                seen.add(cur)
                cur = self.parts[cur].parent
        if not isinstance(self.layers, dict):
            raise ModelError("layers must be an object")
        for name, lay in self.layers.items():
            if not isinstance(lay, dict) or set(lay) - set(LAYER_DEFAULT):
                raise ModelError(f"layer '{name}' may only hold {sorted(LAYER_DEFAULT)}")
            if not (
                _num(lay.get("opacity", 1))
                and _num(lay.get("z_index", 0))
                and isinstance(lay.get("visible", True), bool)
            ):
                raise ModelError(f"layer '{name}': opacity/z_index must be numbers, visible a boolean")
