# backend/app/scene_demo_entities.py
"""Demo objects for the `entity` and `link` kinds (two tiles joined by a link)."""


def entity_demo() -> list[dict]:
    return [
        {"id": "ent-demo-a", "kind": "entity", "shape": "book", "title": "report.pdf", "subtitle": "pdf, 12 pages",
         "accent": "#b48cff", "ref": {"type": "file", "id": "demo0001"}, "pos": [-5, 1.2, 4]},
        {"id": "ent-demo-b", "kind": "entity", "shape": "tool", "title": "summarize_file", "accent": "#ff6b6b",
         "ref": {"type": "tool", "id": "summarize_file"}, "pos": [-1.5, 1.2, 4]},
        {"id": "lnk-demo", "kind": "link", "from": "ent-demo-a", "to": "ent-demo-b", "label": "input", "color": "#4fd8ff"},
    ]
