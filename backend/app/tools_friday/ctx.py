# backend/app/tools_friday/ctx.py
"""Per-connection context handed to Friday's model tools."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.scene import SceneStore

Emit = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class Ctx:
    """What a tool may touch: the scene and the browser WebSocket of one connection."""

    scene: SceneStore
    emit: Emit  # sends one JSON message to the connected browser
