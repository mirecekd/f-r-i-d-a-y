# backend/app/workshop/messages.py
"""Browser messages `workshop_*`: one dispatch function, errors become readable `error` messages (never an exception)."""

from typing import Any

from app.workshop.session import WORKSHOP_ERRORS, WorkshopSession

KINDS = (
    "workshop_new",
    "workshop_open",
    "workshop_leave",
    "workshop_param",
    "workshop_undo",
    "workshop_redo",
    "workshop_snapshot",
)


async def handle_workshop_message(session: WorkshopSession, msg: dict[str, Any]) -> None:
    kind = str(msg.get("t"))
    try:
        if kind == "workshop_snapshot":
            return session.broker.deliver(msg)  # never raises; unmatched replies are dropped
        if kind == "workshop_new":
            title = msg.get("title")
            await session.open(None, title if isinstance(title, str) else None)
        elif kind == "workshop_open":
            await session.open(msg.get("id"))
        elif kind == "workshop_leave":
            await session.leave()
        elif kind in ("workshop_param", "workshop_undo", "workshop_redo"):
            current = session.require()
            if msg.get("id") != current["id"]:
                await session.emit(
                    {
                        "t": "error",
                        "message": f"{kind}: the open workshop is {current['id']}, not {str(msg.get('id'))[:40]!r}",
                    }
                )
            elif kind == "workshop_param":
                await session.param(msg.get("name"), msg.get("value"))
            else:
                await session.step(kind == "workshop_undo")
        else:
            await session.emit({"t": "error", "message": f"unknown message type: {kind}"})
    except WORKSHOP_ERRORS as e:
        await session.emit({"t": "error", "message": f"{kind}: {e}"[:400]})
