# backend/app/scene_schema.py
"""Scene DSL v1 schema: allowed kinds/props and op validation. Raises SceneError on anything unknown."""

MAX_OBJECTS = 5000
MAX_ARRAY = 20000
MAX_URL = 3_000_000
MAX_TEXT = 4000

COMMON = {"id", "kind", "pos", "rot", "scale", "color", "label", "parent", "opacity", "anim", "visible"}
KIND_PROPS: dict[str, set[str]] = {
    "box": set(),
    "sphere": set(),
    "cylinder": set(),
    "cone": set(),
    "torus": set(),
    "plane": set(),
    "group": set(),
    "text": {"text", "size"},
    "label": {"text", "size", "target", "offset"},
    "line": {"from", "to"},
    "polyline": {"pts", "closed"},
    "arrow": {"from", "to", "head"},
    "particles": {"gen", "count", "radius", "seed", "turns", "height", "arms", "spacing", "pts", "size", "color2"},
    "image": {"url", "w", "h"},
    "graph": {"nodes", "edges", "directed", "node_size"},
    "chart3d": {"values", "labels", "gap", "height", "color2", "show_values"},
    "surface": {"data", "fn", "res", "range", "size", "height", "color2"},
    "gltf": {"url", "fit"},
    "extrude": {"walls", "outline", "thickness", "height", "floor"},
    "csg": {"op", "a", "b", "hide_inputs"},
}
ALL_PROPS = COMMON.union(*KIND_PROPS.values())
ANIM_TYPES = {"spin", "bob", "pulse", "orbit"}
ANIM_KEYS = {"type", "speed", "axis", "amp"}
VEC3_PROPS = {"pos", "rot", "from", "to", "offset"}
NUMBER_PROPS = {"opacity", "head", "radius", "count", "seed", "turns", "height", "arms", "spacing",
                "w", "h", "gap", "res", "thickness", "fit", "node_size"}
BOOL_PROPS = {"visible", "hide_inputs", "closed", "directed", "show_values", "floor"}
STRING_PROPS = {"op", "a", "color", "color2", "label", "parent", "target", "gen", "fn", "id", "kind", "text", "url"}
ARRAY_PROPS = {"b", "pts", "nodes", "edges", "values", "labels", "data", "walls", "outline", "range"}
OP_FIELDS = {
    "add": {"op", "obj"},
    "set": {"op", "id", "props", "ms"},
    "del": {"op", "id"},
    "clear": {"op"},
    "camera": {"op", "pos", "look"},
    "explode": {"op", "factor"},
}


class SceneError(ValueError):
    """An op or object that the scene DSL rejects."""


def _is_num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) < 1e9


def _check_vec3(name: str, v: object) -> None:
    if not (isinstance(v, list) and len(v) == 3 and all(_is_num(x) for x in v)):
        raise SceneError(f"{name} must be [x, y, z] numbers")


def _check_anim(v: object) -> None:
    if v is None:
        return
    for a in v if isinstance(v, list) else [v]:
        if not isinstance(a, dict) or a.get("type") not in ANIM_TYPES:
            raise SceneError(f"anim.type must be one of {sorted(ANIM_TYPES)}")
        if set(a) - ANIM_KEYS:
            raise SceneError(f"unknown anim keys: {sorted(set(a) - ANIM_KEYS)}")
        if a.get("axis", "y") not in ("x", "y", "z") or not all(_is_num(a.get(k, 0)) for k in ("speed", "amp")):
            raise SceneError("anim axis must be x|y|z; speed and amp must be numbers")


def _check_value(name: str, v: object) -> None:
    if name in VEC3_PROPS:
        _check_vec3(name, v)
    elif name == "scale":
        if not _is_num(v):
            _check_vec3(name, v)
    elif name == "size":  # number (text/particles) or [w, d] (surface)
        if not (_is_num(v) or (isinstance(v, list) and len(v) == 2 and all(_is_num(x) for x in v))):
            raise SceneError("size must be a number or [w, d]")
    elif name in NUMBER_PROPS and not _is_num(v):
        raise SceneError(f"{name} must be a number")
    elif name in BOOL_PROPS and not isinstance(v, bool):
        raise SceneError(f"{name} must be a boolean")
    elif name in STRING_PROPS and not isinstance(v, str):
        raise SceneError(f"{name} must be a string")
    elif name in ARRAY_PROPS and not (isinstance(v, list) and len(v) <= MAX_ARRAY):
        raise SceneError(f"{name} must be an array of at most {MAX_ARRAY} items")
    elif name == "anim":
        _check_anim(v)
    if name == "url" and isinstance(v, str) and (len(v) > MAX_URL or not v.startswith(("http://", "https://", "data:", "/"))):
        raise SceneError("url must be http(s), a data: URI or an absolute path, and under 3 MB")
    if name in ("text", "label", "fn") and isinstance(v, str) and len(v) > MAX_TEXT:
        raise SceneError(f"{name} is too long")


def check_props(kind: str | None, props: dict, *, allow_identity: bool) -> None:
    """Validate props against a kind (or against every known prop when the kind is not known)."""
    allowed = COMMON | KIND_PROPS[kind] if kind else ALL_PROPS
    if not allow_identity:
        allowed = allowed - {"id", "kind"}
    for name, v in props.items():
        if name not in allowed:
            raise SceneError(f"unknown property '{name}'" + (f" for kind '{kind}'" if kind else ""))
        _check_value(name, v)


def check_obj(obj: object) -> dict:
    if not isinstance(obj, dict):
        raise SceneError("obj must be an object")
    if not isinstance(obj.get("id"), str) or not obj["id"]:
        raise SceneError("obj.id must be a non-empty string")
    if obj.get("kind") not in KIND_PROPS:
        raise SceneError(f"unknown kind '{obj.get('kind')}'; known: {sorted(KIND_PROPS)}")
    check_props(obj["kind"], obj, allow_identity=True)
    return obj


def check_op(op: object) -> dict:
    """Validate one op shape (not store state)."""
    if not isinstance(op, dict) or op.get("op") not in OP_FIELDS:
        raise SceneError(f"unknown op; known: {sorted(OP_FIELDS)}")
    name = op["op"]
    if set(op) - OP_FIELDS[name]:
        raise SceneError(f"unknown fields for op '{name}': {sorted(set(op) - OP_FIELDS[name])}")
    if name == "add":
        check_obj(op.get("obj"))
    elif name in ("set", "del") and not (isinstance(op.get("id"), str) and op["id"]):
        raise SceneError(f"op '{name}' needs a string id")
    if name == "set":
        if not isinstance(op.get("props"), dict):
            raise SceneError("op 'set' needs props")
        if "ms" in op and not _is_num(op["ms"]):
            raise SceneError("ms must be a number")
    elif name == "camera":
        _check_vec3("pos", op.get("pos"))
        if "look" in op:
            _check_vec3("look", op["look"])
    elif name == "explode" and not _is_num(op.get("factor")):
        raise SceneError("explode needs a numeric factor")
    return op
