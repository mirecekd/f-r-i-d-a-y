# backend/app/__init__.py
"""F.R.I.D.A.Y. backend."""

# YYYYMMDD.X = build day + counter of that day. scripts/release.py sets it from the git tags (never edit by hand).
# FRIDAY_VERSION in the environment (set by the Docker build) overrides it at runtime.
__version__ = "20261121.2"
