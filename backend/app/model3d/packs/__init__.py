# backend/app/model3d/packs/__init__.py
"""Registry of domain packs: named generators that turn a spec into part dicts for the model API."""

import importlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

PackFn = Callable[[dict[str, Any]], list[dict[str, Any]]]
LayersFn = Callable[[list[dict[str, Any]]], dict[str, dict[str, Any]]]
_PACKS: dict[str, PackFn] = {}
_INFO: dict[str, "PackInfo"] = {}
# Every pack module registers itself with `register_pack` on import. Add new packs here.
AUTOLOAD = (
    "app.model3d.packs.building",
    "app.model3d.packs.enclosure",
    "app.model3d.packs.pcb",
)


@dataclass
class PackInfo:
    """Discovery data of a pack: example spec for tool descriptions, defaults for a missing/partial spec, model units, layer settings."""

    example: dict[str, Any] = field(default_factory=dict)
    defaults: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    units: str = "mm"
    layers: LayersFn | None = None


def load_all() -> None:
    """Import every autoloaded pack module. Idempotent (modules are imported once)."""
    for module in AUTOLOAD:
        importlib.import_module(module)


def register_pack(name: str, fn: PackFn, *, example: dict[str, Any] | None = None,
                  defaults: Callable[[dict[str, Any]], dict[str, Any]] | None = None, units: str = "mm",
                  layers: LayersFn | None = None) -> None:
    """Register `fn(spec) -> list of part dicts` under `name`; the part dicts follow Part.from_dict.

    `defaults(spec)` returns spec keys that fill gaps of a missing or partial spec; `layers(parts)` returns Model.layers.
    """
    _PACKS[name] = fn
    _INFO[name] = PackInfo(example or {}, defaults, units, layers)


def list_packs() -> list[str]:
    load_all()
    return sorted(_PACKS)


def get_pack(name: str) -> PackFn | None:
    load_all()
    return _PACKS.get(name)


def pack_info(name: str) -> PackInfo:
    load_all()
    return _INFO.get(name) or PackInfo()


def filled_spec(name: str, spec: dict[str, Any] | None) -> dict[str, Any]:
    """`spec` with the pack defaults added for every top-level key the caller left out."""
    spec = dict(spec or {})
    info = pack_info(name)
    return {**(info.defaults(spec) if info.defaults else {}), **spec}


def catalog() -> str:
    """One line per pack with its example spec (compact JSON), for tool descriptions."""
    import json
    return "; ".join(f"{n}: {json.dumps(pack_info(n).example, separators=(',', ':'))}" for n in list_packs())
