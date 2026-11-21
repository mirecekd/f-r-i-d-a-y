# backend/app/workshop/params.py
"""Spec parameters: normalisation with defaults, the evaluation environment and the pure with_params."""

import copy
import math
import re
from typing import Any

from app.workshop.expr import CONSTANTS, FUNCTIONS, MAX_ABS, SpecError, did_you_mean, number
from app.workshop.reader import check_keys, join

MAX_PARAMS = 40
PARAM_KEYS = {"value", "min", "max", "step", "label", "unit"}
NAME_RE = re.compile(r"^[A-Za-z_]\w{0,31}$")


def _param_default_range(value: float) -> tuple[float, float]:
    if value == 0:
        return 0.0, 1.0
    lo, hi = value / 10, value * 5
    return (lo, hi) if lo <= hi else (hi, lo)


def read_params(raw: Any, notes: list[str] | None = None) -> list[dict[str, Any]]:
    """Normalise spec.params into [{name,label,value,min,max,step,unit}]; out-of-range values are clamped with a note."""
    if raw is None:
        return []
    if not isinstance(raw, dict):
        raise SpecError("params: expected an object {name: number | {value,min,max,...}}")
    if len(raw) > MAX_PARAMS:
        raise SpecError(f"params: at most {MAX_PARAMS} parameters, got {len(raw)}")
    out = []
    for name, item in raw.items():
        path = join("params", name)
        if not NAME_RE.match(name) or name in CONSTANTS or name in FUNCTIONS:
            raise SpecError(f"{path}: invalid parameter name (letters, digits, '_'; not a constant or function)")
        body = item if isinstance(item, dict) else {"value": item}
        check_keys(body, PARAM_KEYS, path)
        value = number(body.get("value"), {}, join(path, "value")) if "value" in body else _missing(path)
        dlo, dhi = _param_default_range(value)
        lo = number(body.get("min", dlo), {}, join(path, "min"))
        hi = number(body.get("max", dhi), {}, join(path, "max"))
        if lo > hi:
            raise SpecError(f"{path}: min {lo:g} is greater than max {hi:g}")
        step = number(body.get("step", max(round((hi - lo) / 100, 6), 0.0001)), {}, join(path, "step"))
        if step <= 0:
            raise SpecError(f"{join(path, 'step')}: must be > 0")
        label, unit = body.get("label", name), body.get("unit", "")
        if not isinstance(label, str) or not isinstance(unit, str):
            raise SpecError(f"{path}: label and unit must be text")
        clamped = min(max(value, lo), hi)
        if clamped != value and notes is not None:
            notes.append(f"{path}: value {value:g} clamped to {clamped:g} (range {lo:g}..{hi:g})")
        out.append({"name": name, "label": label, "value": clamped, "min": lo, "max": hi, "step": step, "unit": unit})
    return out


def _missing(path: str) -> float:
    raise SpecError(f"{join(path, 'value')}: required")


def param_env(params: list[dict[str, Any]]) -> dict[str, float]:
    return {p["name"]: float(p["value"]) for p in params}


def with_params(spec: dict, values: dict[str, float]) -> dict:
    """A NEW spec with the given parameter values set, each clamped to the parameter's [min, max]."""
    params = read_params(spec.get("params"))
    known = {p["name"]: p for p in params}
    for name, v in values.items():
        if name not in known:
            raise SpecError(f"params.{name}: unknown parameter" + did_you_mean(name, known))
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or abs(v) > MAX_ABS:
            raise SpecError(f"params.{name}: value must be a finite number")
        known[name]["value"] = min(max(float(v), known[name]["min"]), known[name]["max"])
    out = copy.deepcopy(spec)
    out["params"] = {p["name"]: {k: p[k] for k in ("value", "min", "max", "step", "label", "unit")} for p in params}
    return out
