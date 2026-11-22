# backend/tests/test_undo_stack.py
"""UndoStack: order, redo, redo cleared by a new action, cap of 30, empty stack."""

import asyncio

from app.undo.stack import CAP, UndoEntry, UndoStack


def run(coro):
    return asyncio.run(coro)


def label_of(result: UndoEntry | None) -> str:
    assert result is not None
    return result.label


def entry(log: list[str], name: str) -> UndoEntry:
    async def undo() -> None:
        log.append(f"undo {name}")

    async def redo() -> None:
        log.append(f"redo {name}")

    return UndoEntry(name, undo, redo)


def test_undo_then_redo_in_order():
    log: list[str] = []
    stack = UndoStack()
    stack.push(entry(log, "a"))
    stack.push(entry(log, "b"))
    assert label_of(run(stack.undo())) == "b"
    assert label_of(run(stack.undo())) == "a"
    assert run(stack.undo()) is None
    assert label_of(run(stack.redo())) == "a"
    assert log == ["undo b", "undo a", "redo a"]


def test_new_action_clears_redo():
    log: list[str] = []
    stack = UndoStack()
    stack.push(entry(log, "a"))
    run(stack.undo())
    assert stack.can_redo
    stack.push(entry(log, "b"))
    assert not stack.can_redo
    assert run(stack.redo()) is None


def test_cap_is_30():
    log: list[str] = []
    stack = UndoStack()
    for i in range(CAP + 5):
        stack.push(entry(log, str(i)))
    labels = []
    while (e := run(stack.undo())) is not None:
        labels.append(e.label)
    assert len(labels) == CAP == 30
    assert labels[0] == str(CAP + 4) and labels[-1] == "5"
