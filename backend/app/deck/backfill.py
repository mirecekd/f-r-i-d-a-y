# backend/app/deck/backfill.py
"""Register what was stored before the deck existed (uploads, files, 3D models), once per data directory."""

import logging

from app.deck import db, hooks

log = logging.getLogger("friday.deck")
LIMIT = 500
_done: set[str] = set()


def ensure() -> None:
    """Idempotent and cheap after the first call; failures are logged, never raised."""
    key = str(db.db_path())
    if key in _done:
        return
    _done.add(key)
    try:
        _run()
    except Exception as e:
        log.warning("deck backfill failed: %s: %s", type(e).__name__, e)


def _known() -> set[tuple[str, str]]:
    with db.read() as conn:
        return {(r[0], r[1]) for r in conn.execute("SELECT type, ref_id FROM items")}


def _run() -> None:
    from app.files import store as files
    from app.model3d.store import ModelStore
    from app.vision import store as images

    known = _known()
    for meta in images.list_meta(LIMIT):
        if ("image", meta["id"]) not in known:
            hooks.image_saved(meta)
    for meta in files.list_files(LIMIT):
        if ("file", meta["id"]) not in known:
            try:
                text = files.text_of(meta["id"])
            except OSError:
                text = ""
            hooks.file_saved(meta, text)
    models = ModelStore()
    for model_id in models.list():
        if ("model3d", model_id) not in known:
            try:
                hooks.model_saved(models.load(model_id))
            except Exception as e:  # a corrupt model file must not stop the others
                log.warning("deck backfill: model %s skipped: %s", model_id, e)
