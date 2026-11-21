# backend/app/deck/stored.py
"""Delete the underlying stored object of a deck item (only after the user approved it)."""

import logging

log = logging.getLogger("friday.deck")


def delete_stored(type_: str, ref_id: str) -> bool:
    """Best effort removal from the item's own store; True when something was removed."""
    try:
        if type_ == "model3d":
            from app.model3d.store import ModelStore

            store = ModelStore()
            had = store.exists(ref_id)
            store.delete(ref_id)
            return had
        if type_ == "web":
            from app.webpages import store as web_store

            return web_store.delete(ref_id)
        if type_ in ("image", "file"):
            from app.vision.store import uploads_dir

            folder, removed = uploads_dir(), False
            for path in folder.glob(f"{ref_id}*") if ref_id.isalnum() else []:
                path.unlink(missing_ok=True)
                removed = True
            return removed
    except (OSError, ValueError) as e:
        log.warning("deck: cannot delete stored %s %s: %s", type_, ref_id, e)
    return False
