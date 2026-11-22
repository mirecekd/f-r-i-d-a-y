# backend/app/undo/__init__.py
"""Shared undo / redo: one voice phrase undoes the last action of whichever domain made it."""

from app.undo.tools import UndoService

__all__ = ["UndoService"]
