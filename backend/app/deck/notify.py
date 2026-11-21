# backend/app/deck/notify.py
"""Change listeners: every connection subscribes so the browser gets `deck_changed` when an item changes."""

import logging
import threading
from collections.abc import Callable

log = logging.getLogger("friday.deck")
Listener = Callable[[str], None]  # called with the deck id, from any thread; must not block
_listeners: set[Listener] = set()
_lock = threading.Lock()


def subscribe(fn: Listener) -> None:
    with _lock:
        _listeners.add(fn)


def unsubscribe(fn: Listener) -> None:
    with _lock:
        _listeners.discard(fn)


def notify(deck_id: str) -> None:
    with _lock:
        targets = list(_listeners)
    for fn in targets:
        try:
            fn(deck_id)
        except Exception as e:  # a dead connection must not break registration
            log.debug("deck listener dropped: %s", e)
            unsubscribe(fn)
