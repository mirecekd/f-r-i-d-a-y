# backend/app/undo/stack.py
"""Bounded undo / redo stack of one browser connection."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

CAP = 30

Step = Callable[[], Awaitable[None]]


@dataclass
class UndoEntry:
    label: str  # plain words, e.g. "moved wall_1"
    undo: Step
    redo: Step


class UndoStack:
    """Newest entry last; a new action drops everything that could be redone."""

    def __init__(self, cap: int = CAP) -> None:
        self.cap = cap
        self._done: list[UndoEntry] = []
        self._undone: list[UndoEntry] = []

    def push(self, entry: UndoEntry) -> None:
        self._done.append(entry)
        del self._done[: -self.cap]
        self._undone.clear()

    def clear_redo(self) -> None:
        self._undone.clear()

    @property
    def can_undo(self) -> bool:
        return bool(self._done)

    @property
    def can_redo(self) -> bool:
        return bool(self._undone)

    async def undo(self) -> UndoEntry | None:
        """Run the newest entry's undo; None when there is nothing to undo."""
        if not self._done:
            return None
        entry = self._done.pop()
        try:
            await entry.undo()
        except Exception:
            self._done.append(entry)  # a failed step stays available
            raise
        self._undone.append(entry)
        return entry

    async def redo(self) -> UndoEntry | None:
        if not self._undone:
            return None
        entry = self._undone.pop()
        try:
            await entry.redo()
        except Exception:
            self._undone.append(entry)
            raise
        self._done.append(entry)
        return entry
