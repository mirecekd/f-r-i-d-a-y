# backend/app/workshop/spec.py
"""Public API of the workshop part-tree engine."""

from app.workshop.expand import Expanded, expand
from app.workshop.expr import SpecError
from app.workshop.params import with_params

__all__ = ["Expanded", "SpecError", "expand", "with_params"]
