# backend/app/entities/links.py
"""Link objects between entities: ids, creation and the lookups the tools need."""

import hashlib
from typing import Any

from app.scene import SceneStore
from app.scene_schema import SceneError


def link_id(a: str, b: str) -> str:
    return "lnk-" + hashlib.sha256(f"{a}|{b}".encode()).hexdigest()[:8]


def links_of(scene: SceneStore, entity_id: str | None = None) -> list[dict[str, Any]]:
    return [o for o in scene.objects() if o["kind"] == "link" and (entity_id is None or entity_id in (o["from"], o["to"]))]


def linked_entities(scene: SceneStore, entity_id: str) -> list[dict[str, Any]]:
    """The entity objects on the other end of every link of `entity_id`."""
    by_id = {o["id"]: o for o in scene.objects()}
    others = [o["to"] if o["from"] == entity_id else o["from"] for o in links_of(scene, entity_id)]
    return [by_id[i] for i in others if i in by_id and by_id[i]["kind"] == "entity"]


def make_link(scene: SceneStore, from_id: str, to_id: str, label: str | None, style: str | None) -> tuple[list[dict], str]:
    """The `add` op of a link between two existing objects; raises SceneError for bad endpoints."""
    ids = {o["id"] for o in scene.objects() if o["kind"] != "link"}
    for end in (from_id, to_id):
        if end not in ids:
            raise SceneError(f"unknown object id '{end}'; call entity_list")
    if from_id == to_id:
        raise SceneError("cannot link an object to itself")
    obj: dict[str, Any] = {"id": link_id(from_id, to_id), "kind": "link", "from": from_id, "to": to_id}
    if label:
        obj["label"] = label[:60]
    if style:
        obj["style"] = style
    return [{"op": "add", "obj": obj}], obj["id"]
