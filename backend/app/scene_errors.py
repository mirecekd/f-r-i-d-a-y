# backend/app/scene_errors.py
"""The error every scene DSL validator raises."""


class SceneError(ValueError):
    """An op or object that the scene DSL rejects."""
