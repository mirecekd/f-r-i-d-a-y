# backend/app/assets/__init__.py
"""3D asset catalog: a small curated CC0 index, offline search, on-demand download, scene placement and credits."""

from app.assets.route import router
from app.assets.tools import AssetSession, register_asset_tools

__all__ = ["AssetSession", "register_asset_tools", "router"]
