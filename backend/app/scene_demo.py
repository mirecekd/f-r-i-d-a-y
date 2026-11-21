# backend/app/scene_demo.py
"""Demo scene showing every kind of the scene DSL (sent for {t:'demo', what:'scene'} when FRIDAY_DEMO=1)."""

from app.scene_demo_entities import entity_demo
from app.scene_demo_gltf import tetrahedron_data_uri


def _robot() -> list[dict]:
    c = "#4fd8ff"
    return [
        {"id": "robot", "kind": "group", "pos": [-14, -2.6, 0], "anim": {"type": "bob", "speed": 0.8, "amp": 0.1}},
        {"id": "r-torso", "kind": "box", "parent": "robot", "pos": [0, 1.5, 0], "scale": [1.4, 1.8, 0.8], "color": c},
        {"id": "r-head", "kind": "group", "parent": "robot", "pos": [0, 3.0, 0], "anim": {"type": "spin", "speed": 0.5}},
        {"id": "r-skull", "kind": "sphere", "parent": "r-head", "scale": 1.0, "color": "#7fe8ff"},
        {"id": "r-eye", "kind": "box", "parent": "r-head", "pos": [0, 0.08, 0.45], "scale": [0.7, 0.14, 0.1], "color": "#ffd24a"},
        {"id": "r-arm-l", "kind": "cylinder", "parent": "robot", "pos": [-1.0, 1.7, 0], "scale": [0.35, 1.5, 0.35], "color": "#3dffa0"},
        {"id": "r-arm-r", "kind": "cylinder", "parent": "robot", "pos": [1.0, 1.7, 0], "scale": [0.35, 1.5, 0.35], "color": "#3dffa0"},
        {"id": "r-leg-l", "kind": "cylinder", "parent": "robot", "pos": [-0.4, 0.0, 0], "scale": [0.4, 1.2, 0.4], "color": "#b36bff"},
        {"id": "r-leg-r", "kind": "cylinder", "parent": "robot", "pos": [0.4, 0.0, 0], "scale": [0.4, 1.2, 0.4], "color": "#b36bff"},
        {"id": "r-core", "kind": "sphere", "parent": "robot", "pos": [0, 1.6, 0.45], "scale": 0.35, "color": "#ff9a3d", "anim": {"type": "pulse", "speed": 2}},
        {"id": "r-tag", "kind": "label", "target": "robot", "text": "Robot (groups)"},
    ]


def _floor_plan() -> list[dict]:
    walls = [[0, 0, 8, 0], [8, 0, 8, 6], [8, 6, 0, 6], [0, 6, 0, 0], [3.5, 0, 3.5, 2.2], [3.5, 3.8, 3.5, 6], [3.5, 3, 8, 3]]
    return [
        {"id": "plan", "kind": "extrude", "pos": [-12, -3.2, 6], "walls": walls, "thickness": 0.2, "height": 1.6, "color": "#ffd24a"},
        {"id": "plan-t", "kind": "text", "pos": [-8, -0.6, 9], "text": "Floor plan (extrude)", "size": 0.45, "color": "#ffd24a"},
    ]


def _lathe_demo() -> list[dict]:
    vase = [[0, 0], [0.8, 0], [1.3, 1.2], [0.9, 2.4], [0.5, 3.0], [0.7, 3.4]]
    return [
        {"id": "vase", "kind": "lathe", "pos": [-16, -3.2, 6], "profile": vase, "segments": 32, "color": "#7be0a0"},
        {"id": "vase-t", "kind": "text", "pos": [-16, 0.6, 6], "text": "Vase (lathe)", "size": 0.45, "color": "#7be0a0"},
    ]


def _csg_demo() -> list[dict]:
    return [
        {"id": "csg-a", "kind": "box", "pos": [-12, 3, 12], "scale": [3, 2, 2], "color": "#4fd8ff"},
        {"id": "csg-b", "kind": "cylinder", "pos": [-12, 3, 13], "rot": [1.5708, 0, 0], "scale": [1, 2, 1], "color": "#05070a"},
        {"id": "csg", "kind": "csg", "op": "subtract", "a": "csg-a", "b": ["csg-b"], "hide_inputs": True, "color": "#4fd8ff"},
    ]


def _network() -> list[dict]:
    nodes = [
        {"id": "web", "label": "Web", "pos": [0, 2, 0], "color": "#4fd8ff", "size": 0.7},
        {"id": "api", "label": "API", "pos": [3, 3.2, 1], "color": "#3dffa0", "size": 0.8},
        {"id": "auth", "label": "Auth", "pos": [3, 0.6, -2], "color": "#ff9a3d"},
        {"id": "db", "label": "DB", "pos": [6.5, 2, 0], "color": "#b36bff", "size": 0.8},
        {"id": "queue", "label": "Queue", "pos": [6, 4.5, 2.5], "color": "#ff5ea8"},
    ]
    edges = [["web", "api"], ["api", "auth"], ["api", "db"], ["api", "queue"], ["queue", "db"]]
    return [{"id": "net", "kind": "graph", "pos": [-2, -2, -4], "nodes": nodes, "edges": edges, "directed": True}]


def _charts() -> list[dict]:
    return [
        {"id": "bars", "kind": "chart3d", "pos": [-8, -3.2, -6], "values": [3, 7, 4, 9, 6], "labels": ["Q1", "Q2", "Q3", "Q4", "Q5"], "color": "#4fd8ff", "color2": "#ff5ea8", "height": 3.5},
        {"id": "surf", "kind": "surface", "pos": [8, -3.0, -4], "fn": "sin(x)*cos(z)", "range": [-3.2, 3.2], "size": [6, 6], "height": 2, "color": "#4fd8ff", "color2": "#ff7ad9"},
        {"id": "gal", "kind": "particles", "pos": [-12, 7, -12], "rot": [0.5, 0, 0.25], "gen": "galaxy", "count": 4000, "radius": 4, "color": "#ffd24a", "color2": "#4fd8ff", "anim": {"type": "spin", "speed": 0.15}},
        {"id": "spiral", "kind": "particles", "pos": [-2, 4, -10], "gen": "spiral", "count": 700, "radius": 1.4, "height": 3, "color": "#3dffa0", "size": 0.07, "anim": {"type": "spin", "speed": 0.6}},
    ]


def _shapes() -> list[dict]:
    return [
        {"id": "s-torus", "kind": "torus", "pos": [0, 0, 11], "scale": 1.6, "color": "#b36bff", "anim": {"type": "spin", "speed": 0.8, "axis": "x"}},
        {"id": "s-cone", "kind": "cone", "pos": [4, -2.4, 11], "scale": [1, 1.6, 1], "color": "#3dffa0"},
        {"id": "s-plane", "kind": "plane", "pos": [7.5, -1.8, 11], "rot": [0, -0.6, 0], "scale": 1.5, "color": "#ff9a3d"},
        {"id": "s-orbiter", "kind": "sphere", "pos": [0, 0, 11], "scale": 0.3, "color": "#ffd24a", "anim": {"type": "orbit", "speed": 1.5, "amp": 1.6, "axis": "y"}},
        {"id": "s-line", "kind": "line", "from": [-2, -3, 15], "to": [3, -3, 15], "color": "#8fe8ff"},
        {"id": "s-poly", "kind": "polyline", "pts": [[4, -3, 15], [5, -2, 15], [6, -3, 15], [7, -2, 15], [8, -3, 15]], "color": "#ff5ea8"},
        {"id": "s-arrow", "kind": "arrow", "from": [-2, -2.4, 13.5], "to": [3, -0.6, 13.5], "color": "#ffd24a"},
        {"id": "s-img", "kind": "image", "pos": [6, 5, -12], "w": 3, "h": 1.6, "url": "data:image/svg+xml;utf8," +
            "<svg xmlns='http://www.w3.org/2000/svg' width='300' height='160'><rect width='300' height='160' fill='%23062033'/><circle cx='80' cy='80' r='50' fill='%234fd8ff'/><rect x='150' y='40' width='110' height='80' fill='%23ff9a3d'/></svg>"},
        {"id": "s-gltf", "kind": "gltf", "pos": [11, 0, 9], "url": tetrahedron_data_uri(), "fit": 1.6, "color": "#ffffff", "anim": {"type": "spin", "speed": 0.7}},
        {"id": "s-title", "kind": "text", "pos": [0, 8, -6], "text": "FRIDAY scene DSL v1", "size": 0.8, "color": "#8fe8ff"},
    ]


def demo_objects() -> list[dict]:
    return _robot() + _floor_plan() + _lathe_demo() + _csg_demo() + _network() + _charts() + _shapes() + entity_demo()


DEMO_CAMERA = {"op": "camera", "pos": [-1, 8, 30], "look": [-1, -1, 0]}
