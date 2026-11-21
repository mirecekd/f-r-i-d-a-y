# backend/app/deck/__init__.py
"""The deck: a persistent registry (SQLite) of everything the user saved or Friday created.

`from app import deck; deck.register("image", ref_id, title, ...)` is the stable entry point for other modules."""

from app.deck.items import SOURCES, TYPES, DeckError, item_id
from app.deck.query import count_items, find, get, list_items, resolve, stats
from app.deck.registry import delete, register, update

__all__ = ["SOURCES", "TYPES", "DeckError", "item_id", "count_items", "find", "get", "list_items", "resolve", "stats",
           "delete", "register", "update"]
