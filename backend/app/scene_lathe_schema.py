# backend/app/scene_lathe_schema.py
"""Validation of the `lathe` scene props: `profile` [[r, y], ...], `segments` and `cap`."""

import math

from app.scene_errors import SceneError

MIN_PROFILE, MAX_PROFILE = 2, 64
MIN_SEGMENTS, MAX_SEGMENTS = 3, 96
MAX_COORD = 1e4


def _is_coord(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and abs(v) < MAX_COORD


def check_lathe_value(name: str, v: object) -> bool:
    """Validate the props this module owns; returns True when `name` was handled here."""
    if name == "profile":
        if not (isinstance(v, list) and MIN_PROFILE <= len(v) <= MAX_PROFILE):
            raise SceneError(f"profile must be a list of {MIN_PROFILE}..{MAX_PROFILE} [r, y] points")
        for p in v:
            if not (isinstance(p, list) and len(p) == 2 and all(_is_coord(x) for x in p)):
                raise SceneError(f"profile points must be [r, y] finite numbers below {MAX_COORD:g}")
            if p[0] < 0:
                raise SceneError("profile radius r must be >= 0")
        return True
    if name == "segments":
        if not (isinstance(v, int) and not isinstance(v, bool) and MIN_SEGMENTS <= v <= MAX_SEGMENTS):
            raise SceneError(f"segments must be an integer {MIN_SEGMENTS}..{MAX_SEGMENTS}")
        return True
    if name == "cap":
        if not isinstance(v, bool):
            raise SceneError("cap must be a boolean")
        return True
    return False
