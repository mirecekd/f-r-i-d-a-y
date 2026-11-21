# backend/app/scene.py
"""Server-side scene state: the single source of truth the model edits via patches."""

from app.scene_describe import describe_scene
from app.scene_schema import MAX_OBJECTS, SceneError, check_op, check_props

__all__ = ["SceneStore", "SceneError"]


class SceneStore:
    def __init__(self) -> None:
        self._objs: dict[str, dict] = {}
        self.selected: list[str] = []
        self.camera: dict | None = None
        self.explode: float = 0.0

    def objects(self) -> list[dict]:
        return list(self._objs.values())

    def apply(self, ops: list[dict]) -> None:
        """Validate every op against a copy, then commit. On SceneError nothing changes."""
        if not isinstance(ops, list):
            raise SceneError("ops must be a list")
        work = dict(self._objs)
        camera, explode = self.camera, self.explode
        for i, op in enumerate(ops):
            try:
                check_op(op)
                camera, explode = self._step(work, op, camera, explode)
            except SceneError as e:
                raise SceneError(f"op #{i}: {e}") from e
        if len(work) > MAX_OBJECTS:
            raise SceneError(f"scene would hold {len(work)} objects; the limit is {MAX_OBJECTS}")
        self._objs, self.camera, self.explode = work, camera, explode
        self.selected = [i for i in self.selected if i in work]

    @staticmethod
    def _step(work: dict[str, dict], op: dict, camera: dict | None, explode: float):
        name = op["op"]
        if name == "add":
            work[op["obj"]["id"]] = dict(op["obj"])
        elif name == "set":
            cur = work.get(op["id"])
            check_props(cur["kind"] if cur else None, op["props"], allow_identity=False)
            if cur is not None:
                work[op["id"]] = {**cur, **op["props"]}
        elif name == "del":
            doomed = {op["id"]}
            grew = True
            while grew:
                kids = {i for i, o in work.items() if o.get("parent") in doomed} - doomed
                grew = bool(kids)
                doomed |= kids
            for i in doomed:
                work.pop(i, None)
        elif name == "clear":
            work.clear()
        elif name == "camera":
            camera = {"pos": op["pos"], "look": op.get("look", [0, 0, 0])}
        elif name == "explode":
            explode = float(op["factor"])
        return camera, explode

    def select(self, ids: list) -> None:
        """Record the browser's selection; unknown ids are dropped."""
        self.selected = [str(i) for i in ids if str(i) in self._objs][:200]

    def describe(self, max_lines: int = 200) -> str:
        return describe_scene(self._objs, self.selected, self.camera, self.explode, max_lines)
