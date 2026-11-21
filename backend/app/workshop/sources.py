# backend/app/workshop/sources.py
"""Reference material of a workshop: deck items listed in the record's `sources` and shown as tiles around the table."""

import math
from typing import Any

from app.deck import db, query
from app.deck.place import entity_spec
from app.entities.layout import BASE_Y, SPACING
from app.entities.make import add_entity, entity_id
from app.tools_friday.ctx import Ctx
from app.workshop import stage, store

SUMMARY_CHARS = 600
RING_GAP = 1.2  # tiles stand this far outside the table edge
CLEAN_REACH = stage.MAX_RADIUS + RING_GAP + 2.0  # entity tiles within this reach of the origin belong to the workshop


def _ids(raw: object, field: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list) or not all(isinstance(i, str) and i.strip() for i in raw):
        raise store.WorkshopError(f"{field} must be a list of deck ids")
    return list(dict.fromkeys(i.strip() for i in raw))


def add(rec: dict[str, Any], ids: object) -> list[str]:
    """Add deck items (full ids or unique prefixes) to `rec['sources']`; returns the new list. Nothing changes on an error."""
    found: list[str] = []
    for ref in _ids(ids, "add"):
        item = query.resolve(ref)
        if item is None:
            raise store.WorkshopError(f"unknown deck item {ref[:60]!r}; call deck_list or deck_find")
        found.append(item["id"])
    merged = list(dict.fromkeys([*rec["sources"], *found]))
    if len(merged) > store.MAX_SOURCES:
        raise store.WorkshopError(
            f"a workshop holds at most {store.MAX_SOURCES} sources ({len(merged)} requested); remove some first"
        )
    rec["sources"] = merged
    return merged


def remove(rec: dict[str, Any], ids: object) -> list[str]:
    """Take items out of `rec['sources']` (ids that are not sources are ignored); returns the new list."""
    gone: set[str] = set()
    for ref in _ids(ids, "remove"):
        item = query.resolve(ref)
        gone.add(item["id"] if item else ref)
    rec["sources"] = [d for d in rec["sources"] if d not in gone]
    return rec["sources"]


def drop_dead(rec: dict[str, Any]) -> list[str]:
    """Drop sources that left the deck (deck_forget); returns the notes about it."""
    dead = [d for d in rec["sources"] if query.get(d) is None]
    if dead:
        rec["sources"] = [d for d in rec["sources"] if d not in dead]
        store.save(rec)
    return [f"source {d} is no longer on the deck and was dropped" for d in dead]


def _text_of(deck_id: str) -> str:
    with db.read() as conn:
        row = conn.execute("SELECT text FROM items WHERE id = ?", (deck_id,)).fetchone()
    return str(row["text"]) if row else ""


def describe(rec: dict[str, Any]) -> list[dict[str, Any]]:
    """[{deck_id, entity_id, title, kind, summary}] of the live sources; entity_id is None for items without a tile."""
    out: list[dict[str, Any]] = []
    for deck_id in rec["sources"]:
        item = query.get(deck_id)
        if item is None:
            continue
        spec = entity_spec(item)
        summary = " ".join(p for p in (item["subtitle"], _text_of(deck_id)) if p)
        out.append(
            {
                "deck_id": deck_id,
                "entity_id": None if "error" in spec else entity_id(spec["ref_type"], spec["ref_id"]),
                "title": item["title"],
                "kind": item["type"],
                "summary": summary[:SUMMARY_CHARS],
            }
        )
    return out


def tiles(rec: dict[str, Any]) -> list[dict[str, str]]:
    """The `sources` of the `enter` message."""
    return [{"entity_id": d["entity_id"], "title": d["title"], "kind": d["kind"]} for d in describe(rec) if d["entity_id"]]


def _table_radius(ctx: Ctx, workshop_id: str) -> float:
    plate = next((o for o in ctx.scene.objects() if o["id"] == f"ws:{workshop_id}:platform"), None)
    return plate["scale"][0] / 2 if plate and plate.get("scale") else stage.MIN_RADIUS


def ring_positions(count: int, center: tuple[float, float, float], table: float) -> list[list[float]]:
    """`count` tile positions on a circle around `center`, outside the table, starting behind it."""
    radius = table + RING_GAP
    if count > 1:
        radius = max(radius, SPACING / (2 * math.sin(math.pi / count)))
    return [
        [
            round(center[0] + radius * math.cos(-math.pi / 2 + 2 * math.pi * i / count), 3),
            BASE_Y,
            round(center[2] + radius * math.sin(-math.pi / 2 + 2 * math.pi * i / count), 3),
        ]
        for i in range(count)
    ]


async def place(ctx: Ctx, rec: dict[str, Any]) -> list[str]:
    """Stand each source as an entity tile around the table and remove tiles of sources that are gone.

    Idempotent: a tile already at its place is left alone. Returns the entity ids of the placed tiles."""
    origin = store.origin_of(rec["origin_n"])
    wanted = [(d, spec) for d in describe(rec) if d["entity_id"] for spec in [entity_spec(query.get(d["deck_id"]) or {})]]
    spots = ring_positions(len(wanted), origin, _table_radius(ctx, rec["id"]))
    keep = {d["entity_id"] for d, _ in wanted}
    stale = [
        {"op": "del", "id": o["id"]}
        for o in ctx.scene.objects()
        if o["kind"] == "entity"
        and o["id"] not in keep
        and (o.get("ref") or {}).get("type") != "workshop"
        and o.get("pos")
        and math.hypot(o["pos"][0] - origin[0], o["pos"][2] - origin[2]) <= CLEAN_REACH
    ]
    if stale:
        ctx.scene.apply(stale)
        await ctx.emit({"t": "scene", "ops": stale})
    for (d, spec), pos in zip(wanted, spots, strict=True):
        old = next((o for o in ctx.scene.objects() if o["id"] == d["entity_id"]), None)
        if old is not None and old.get("pos") == pos:
            continue
        result = await add_entity(ctx.scene, ctx.emit, **spec, pos=pos)
        if "error" in result:
            raise store.WorkshopError(f"cannot place source {d['title']!r}: {result['error']}")
    return [d["entity_id"] for d, _ in wanted]
